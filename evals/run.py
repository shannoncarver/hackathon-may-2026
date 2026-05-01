"""Eval harness for LINQ Hackathon agent definitions.

Usage:
    python evals/run.py                        # all agents, all cases
    python evals/run.py --agent 17-eng-ai      # single agent
    python evals/run.py --ci                   # exit non-zero on any schema failure

Pattern: per-agent JSONL datasets in evals/per-agent/<agent>/cases.jsonl,
each case scored by (a) deterministic schema validation against
schemas/agents/<agent>.schema.json and (b) a single-dimension LLM-judge
rubric from evals/judges/<rubric>.md.

Reports written to evals/reports/<date>-<run-id>.md.

Per Anthropic guidance (https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents):
  - Multi-dimensional rubrics scored in isolation (one judge call per dimension).
  - Judge model and prompt are pinned; bumping requires recalibration.
  - Counter judge bias: cap output length seen by judge, randomize pairwise order.
  - "Unknown" escape hatch in every rubric.

For tool-using agents (those with MCP servers or Edit/Write tools), this runner
exercises the prompt's reasoning only — it does not invoke tools. End-to-end
coverage with real tool calls lives in evals/e2e/ (Inspect AI, follow-up PR).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic
import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
JUDGE_MODEL = "claude-opus-4-7"   # pinned — bumping requires recalibration
SUT_MODEL = "claude-opus-4-7"
JUDGE_OUTPUT_CAP = 2000           # chars; counters verbosity bias

client = anthropic.Anthropic()


@dataclass
class Case:
    id: str
    input: str
    expected: dict[str, Any] = field(default_factory=dict)
    judge_rubric: str = "code-quality"


@dataclass
class CaseResult:
    case_id: str
    output: str
    schema_pass: bool
    schema_errors: list[str]
    judge_score: float | None
    judge_reasoning: str
    duration_ms: int


def load_agent(agent_name: str) -> tuple[dict[str, Any], str]:
    """Parse the YAML frontmatter and body of an agent definition."""
    path = REPO_ROOT / ".claude" / "agents" / f"{agent_name}.md"
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError(f"No frontmatter in {path}")
    frontmatter = yaml.safe_load(match.group(1))
    body = match.group(2).strip()
    return frontmatter, body


def load_schema(agent_name: str) -> dict[str, Any]:
    return json.loads(
        (REPO_ROOT / "schemas" / "agents" / f"{agent_name}.schema.json").read_text()
    )


def load_cases(agent_name: str) -> list[Case]:
    path = REPO_ROOT / "evals" / "per-agent" / agent_name / "cases.jsonl"
    if not path.exists():
        return []
    return [
        Case(**json.loads(line))
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def load_judge_rubric(rubric_name: str) -> str:
    return (REPO_ROOT / "evals" / "judges" / f"{rubric_name}.md").read_text()


def call_agent(system_prompt: str, user_input: str) -> tuple[str, int]:
    """Single-turn agent call with prompt caching on the system prompt."""
    t0 = time.monotonic()
    response = client.messages.create(
        model=SUT_MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_input}],
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    text = "".join(b.text for b in response.content if b.type == "text")
    return text, duration_ms


def score_schema(output: str, schema: dict[str, Any]) -> tuple[bool, list[str]]:
    """Deterministic scorer: extract JSON from output and validate against schema."""
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", output, re.DOTALL)
    if not json_match:
        json_match = re.search(r"(\{.*\})", output, re.DOTALL)
    if not json_match:
        return False, ["no JSON object found in output"]
    try:
        parsed = json.loads(json_match.group(1))
    except json.JSONDecodeError as e:
        return False, [f"invalid JSON: {e}"]
    errors = [e.message for e in Draft202012Validator(schema).iter_errors(parsed)]
    return len(errors) == 0, errors


def score_judge(output: str, rubric: str, case: Case) -> tuple[float | None, str]:
    """LLM-as-judge scorer with Unknown escape hatch."""
    capped = output[:JUDGE_OUTPUT_CAP]
    judge_prompt = f"""{rubric}

The agent was given this input:
---
{case.input}
---

The agent produced this output (capped at {JUDGE_OUTPUT_CAP} chars to counter verbosity bias):
---
{capped}
---

Return a JSON object with two keys: `score` (1-5 integer, or "Unknown" if you cannot tell) and `reasoning` (1-2 sentences).
"""
    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": judge_prompt}],
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if not json_match:
        return None, f"judge output not parseable: {text[:200]}"
    try:
        parsed = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return None, f"judge JSON invalid: {text[:200]}"
    score = parsed.get("score")
    reasoning = parsed.get("reasoning", "")
    if score == "Unknown" or not isinstance(score, (int, float)):
        return None, reasoning
    return float(score), reasoning


def run_case(
    agent_name: str, system_prompt: str, schema: dict[str, Any], case: Case
) -> CaseResult:
    output, duration_ms = call_agent(system_prompt, case.input)
    schema_pass, schema_errors = score_schema(output, schema)
    rubric = load_judge_rubric(case.judge_rubric)
    judge_score, judge_reasoning = score_judge(output, rubric, case)
    return CaseResult(
        case_id=case.id,
        output=output,
        schema_pass=schema_pass,
        schema_errors=schema_errors,
        judge_score=judge_score,
        judge_reasoning=judge_reasoning,
        duration_ms=duration_ms,
    )


def write_report(run_id: str, results: dict[str, list[CaseResult]]) -> Path:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = REPO_ROOT / "evals" / "reports" / f"{date}-{run_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Eval Run {run_id}",
        f"_{datetime.now(timezone.utc).isoformat()}_",
        "",
    ]
    for agent, agent_results in results.items():
        passes = sum(1 for r in agent_results if r.schema_pass)
        scored = [r.judge_score for r in agent_results if r.judge_score is not None]
        avg = sum(scored) / len(scored) if scored else 0.0
        lines += [
            f"## {agent}",
            "",
            f"Schema pass: **{passes}/{len(agent_results)}** | "
            f"Judge avg: **{avg:.2f}/5** | "
            f"Unknown: {len(agent_results) - len(scored)}",
            "",
            "| Case | Schema | Judge | Notes |",
            "| --- | --- | --- | --- |",
        ]
        for r in agent_results:
            schema_cell = (
                "OK" if r.schema_pass else f"FAIL: {'; '.join(r.schema_errors)[:80]}"
            )
            judge_cell = f"{r.judge_score:.1f}/5" if r.judge_score is not None else "Unknown"
            notes = r.judge_reasoning.replace("\n", " ")[:100]
            lines.append(f"| {r.case_id} | {schema_cell} | {judge_cell} | {notes} |")
        lines.append("")
    path.write_text("\n".join(lines))
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", help="Run a single agent's eval set")
    parser.add_argument("--ci", action="store_true", help="Exit non-zero on any schema failure")
    args = parser.parse_args()

    agents_dir = REPO_ROOT / ".claude" / "agents"
    agent_names = (
        [args.agent] if args.agent else sorted(p.stem for p in agents_dir.glob("*.md"))
    )

    run_id = uuid.uuid4().hex[:8]
    results: dict[str, list[CaseResult]] = {}
    any_failures = False

    for agent_name in agent_names:
        try:
            _, body = load_agent(agent_name)
            schema = load_schema(agent_name)
            cases = load_cases(agent_name)
        except FileNotFoundError as e:
            print(f"WARN  {agent_name}: {e}", file=sys.stderr)
            continue
        if not cases:
            print(f"INFO  {agent_name}: no cases", file=sys.stderr)
            continue

        agent_results: list[CaseResult] = []
        for case in cases:
            print(f"  {agent_name}/{case.id} ...", end=" ", flush=True)
            r = run_case(agent_name, body, schema, case)
            agent_results.append(r)
            mark = "OK  " if r.schema_pass else "FAIL"
            judge = f"{r.judge_score}" if r.judge_score is not None else "Unknown"
            print(f"{mark} schema, judge={judge} ({r.duration_ms}ms)")
            if not r.schema_pass:
                any_failures = True

        results[agent_name] = agent_results

    report_path = write_report(run_id, results)
    print(f"\nReport: {report_path.relative_to(REPO_ROOT)}")
    return 1 if (args.ci and any_failures) else 0


if __name__ == "__main__":
    sys.exit(main())
