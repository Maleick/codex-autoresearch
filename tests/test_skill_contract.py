from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_skill_contract_mentions_runtime_hard_invariants():
    skill_path = REPO_ROOT / "SKILL.md"
    runtime_path = REPO_ROOT / "references/runtime-hard-invariants.md"

    skill_text = skill_path.read_text(encoding="utf-8")
    runtime_text = runtime_path.read_text(encoding="utf-8")

    assert "references/runtime-hard-invariants.md" in skill_text
    assert "Use this checklist when a run starts, resumes, or feels out of sync." in runtime_text
    assert "- Re-state the goal, scope, metric, and verify command before making the next change." in runtime_text
    assert "- If the current state no longer matches reality, stop and surface the mismatch instead of guessing." in runtime_text


def test_skill_contract_tracks_subagent_first_maintenance_expectations():
    contributing_path = REPO_ROOT / "CONTRIBUTING.md"
    feature_list_path = REPO_ROOT / "feature-list.json"

    contributing_text = contributing_path.read_text(encoding="utf-8")
    feature_list = json.loads(feature_list_path.read_text(encoding="utf-8"))

    assert "Subagent-First Skill Contract" in contributing_text
    assert "tests/test_skill_contract.py" in contributing_text
    assert "feature-list.json" in contributing_text
    assert "lightweight contract test" in contributing_text

    entry = next(item for item in feature_list if item["id"] == "subagent_first_skill_contract")
    assert entry["status"] == "complete"
    assert "subagent-first" in entry["name"].lower()
    assert "contributor expectations" in entry["name"].lower()


def test_skill_contract_makes_orchestrator_the_authoritative_state_owner():
    wizard_text = (REPO_ROOT / "references/interaction-wizard.md").read_text(encoding="utf-8")
    logging_text = (REPO_ROOT / "references/results-logging.md").read_text(encoding="utf-8")
    state_text = (REPO_ROOT / "references/state-management.md").read_text(encoding="utf-8")
    subagent_text = (REPO_ROOT / "references/subagent-orchestration.md").read_text(encoding="utf-8")

    assert "standing subagent pool" in wizard_text
    assert "orchestrator writes the authoritative iteration row" in logging_text
    assert "The orchestrator is the only agent that mutates `autoresearch-state.json`" in state_text
    assert "Only the orchestrator records iterations" in subagent_text


def test_skill_contract_restates_post_launch_continuation_boundary():
    skill_text = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
    launcher_text = (REPO_ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
    plugin_manifest = json.loads((REPO_ROOT / "plugins/codex-autoresearch/.codex-plugin/plugin.json").read_text(encoding="utf-8"))

    assert "After launch, continue by default" in skill_text
    assert "continue by default until the user stops the run" in launcher_text
    assert "pre-launch approval" in plugin_manifest["description"]
    assert "continued execution by default after launch" in plugin_manifest["interface"]["longDescription"]
