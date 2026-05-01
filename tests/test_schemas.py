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
