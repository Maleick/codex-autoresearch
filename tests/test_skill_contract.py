from __future__ import annotations

from pathlib import Path


def test_skill_contract_mentions_runtime_hard_invariants():
    skill_path = Path(__file__).resolve().parents[1] / "SKILL.md"
    runtime_path = Path(__file__).resolve().parents[1] / "references/runtime-hard-invariants.md"

    skill_text = skill_path.read_text(encoding="utf-8")
    runtime_text = runtime_path.read_text(encoding="utf-8")

    assert "references/runtime-hard-invariants.md" in skill_text
    assert "Use this checklist when a run starts, resumes, or feels out of sync." in runtime_text
    assert "- Re-state the goal, scope, metric, and verify command before making the next change." in runtime_text
    assert "- If the current state no longer matches reality, stop and surface the mismatch instead of guessing." in runtime_text
