from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "SKILL.md"
BUNDLED_SKILL_PATH = REPO_ROOT / "plugins" / "codex-autoresearch" / "skills" / "codex-autoresearch" / "SKILL.md"
AGENT_METADATA_PATH = REPO_ROOT / "agents" / "openai.yaml"
PLUGIN_README_PATH = REPO_ROOT / "plugins" / "codex-autoresearch" / "README.md"
PLUGIN_MANIFEST_PATH = REPO_ROOT / "plugins" / "codex-autoresearch" / ".codex-plugin" / "plugin.json"
CONTRIBUTING_PATH = REPO_ROOT / "CONTRIBUTING.md"


def test_skill_contract_mentions_runtime_hard_invariants():
    runtime_path = REPO_ROOT / "references/runtime-hard-invariants.md"
    subagent_path = REPO_ROOT / "references" / "subagent-orchestration.md"

    skill_text = SKILL_PATH.read_text(encoding="utf-8")
    bundled_skill_text = BUNDLED_SKILL_PATH.read_text(encoding="utf-8")
    runtime_text = runtime_path.read_text(encoding="utf-8")
    subagent_text = subagent_path.read_text(encoding="utf-8")

    assert skill_text == bundled_skill_text
    assert "references/subagent-orchestration.md" in skill_text
    assert "references/runtime-hard-invariants.md" in skill_text
    assert "standing subagent pool" in skill_text
    assert "After launch, continue by default" in skill_text
    assert "Use this checklist when a run starts, resumes, or feels out of sync." in runtime_text
    assert "- Re-state the goal, scope, metric, and verify command before making the next change." in runtime_text
    assert "- If the current state no longer matches reality, stop and surface the mismatch instead of guessing." in runtime_text
    assert "Only the orchestrator records iterations" in subagent_text


def test_skill_contract_mentions_packaged_skill_and_plugin_wording():
    skill_text = SKILL_PATH.read_text(encoding="utf-8")
    agent_text = AGENT_METADATA_PATH.read_text(encoding="utf-8")
    plugin_readme = PLUGIN_README_PATH.read_text(encoding="utf-8")
    plugin_manifest = json.loads(PLUGIN_MANIFEST_PATH.read_text(encoding="utf-8"))
    contributing_text = CONTRIBUTING_PATH.read_text(encoding="utf-8")

    assert "Prefer the bundled helpers over manual edits to run artifacts." in skill_text
    assert "Treat the repository root as the source of truth for this skill bundle." in skill_text
    assert "standing pool of subagents" in agent_text
    assert "continue by default until the user stops the run" in agent_text
    assert "Treat the repo root as authoritative for behavior and documentation changes" in plugin_readme
    assert "subagent-first flow" in plugin_readme
    assert "python3 scripts/sync_plugin_payload.py" in plugin_readme
    assert plugin_manifest["skills"] == "./skills/codex-autoresearch"
    assert plugin_manifest["description"].startswith("Codex skill bundle for subagent-first")
    assert plugin_manifest["interface"]["shortDescription"] == (
        "Run subagent-first foreground or background improve-verify loops."
    )
    assert "continued execution by default after launch" in plugin_manifest["interface"]["longDescription"]
    assert "Subagent-First Contract" in contributing_text
    assert "tests/test_skill_contract.py" in contributing_text
