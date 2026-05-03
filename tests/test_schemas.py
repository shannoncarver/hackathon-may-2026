"""Tests that every agent schema is valid draft 2020-12 and a sample output validates."""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schemas" / "agents"


@pytest.mark.parametrize("schema_path", list(SCHEMA_DIR.glob("*.schema.json")))
def test_schema_is_valid_draft_2020_12(schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text())
    Draft202012Validator.check_schema(schema)


def test_eng_ai_sample_output_validates() -> None:
    schema = json.loads((SCHEMA_DIR / "17-eng-ai.schema.json").read_text())
    sample = {
        "contract_version": "1.0.0",
        "summary": "Reviewed the proposed agent definition.",
        "findings": [
            {
                "kind": "convention-violation",
                "severity": "low",
                "target": ".claude/agents/docs.md",
                "evidence": "frontmatter description is one sentence; project convention is trigger-rich.",
                "recommendation": "Expand description to include trigger phrases.",
            }
        ],
        "artifacts": [],
        "references": [
            {
                "url": "https://github.com/anthropics/skills/tree/main/skills/skill-creator",
                "relevance": "canonical example of trigger-rich descriptions",
            }
        ],
        "next_steps": [
            {
                "owner": "user",
                "action": "Approve or amend the suggested description rewrite.",
                "why": "Description is what Claude matches for delegation; getting it right unblocks the rest.",
            }
        ],
    }
    Draft202012Validator(schema).validate(sample)


def test_knowledge_curator_v2_sample_output_validates() -> None:
    """Regression test for the v2.0.0 contract introduced by Decision 0013.

    Exercises the new bucket_decision='entity' enum and the updated
    artifacts[].kind values (entity, source-summary, raw-copy, log-entry,
    index-update). Guards against accidental rollback to v1.
    """
    schema = json.loads((SCHEMA_DIR / "40-knowledge-curator.schema.json").read_text())
    sample = {
        "contract_version": "2.0.0",
        "summary": "Ingested Anthropic sub-agents doc; created one entity, one source summary, one raw capture; updated log and index.",
        "bucket_decision": "entity",
        "target_path": "knowledge/wiki/entities/sub-agent.md",
        "artifacts": [
            {
                "path": "knowledge/raw/sources/anthropic-sub-agents-2026-05-03.md",
                "kind": "raw-copy",
                "change": "created",
                "excerpt": "Condensed-with-citation copy of the public Claude Code sub-agents doc.",
            },
            {
                "path": "knowledge/wiki/sources/anthropic-sub-agents.md",
                "kind": "source-summary",
                "change": "created",
            },
            {
                "path": "knowledge/wiki/entities/sub-agent.md",
                "kind": "entity",
                "change": "created",
            },
            {
                "path": "knowledge/wiki/log.md",
                "kind": "log-entry",
                "change": "modified",
            },
            {
                "path": "knowledge/wiki/index.md",
                "kind": "index-update",
                "change": "modified",
            },
        ],
        "gaps": [],
        "references": [
            {
                "url": "https://code.claude.com/docs/en/sub-agents",
                "relevance": "canonical Anthropic source for the sub-agent primitive; ingested as the worked example for Decision 0013",
            }
        ],
        "next_steps": [
            {
                "owner": "user",
                "action": "Confirm the worked example renders correctly from index → entity → source → raw.",
                "why": "Verifies the three-layer wiki pattern resolves end-to-end before further ingest.",
            }
        ],
    }
    Draft202012Validator(schema).validate(sample)
