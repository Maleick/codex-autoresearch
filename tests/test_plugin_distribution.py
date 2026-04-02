from __future__ import annotations

import json
from pathlib import Path

from scripts.check_plugin_distribution import validate_distribution


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "codex-autoresearch"
PLUGIN_MANIFEST = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
PLUGIN_SKILL_ROOT = PLUGIN_ROOT / "skills" / "codex-autoresearch"
MARKETPLACE_PATH = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
SELF_IMPROVEMENT_PARITY_FILES = {
    "SKILL.md": [
        "autoresearch-self-improvement.md",
        "autoresearch-memory.md",
    ],
    "scripts/autoresearch_helpers.py": [
        "DEFAULT_SELF_IMPROVEMENT_PATH",
        "DEFAULT_MEMORY_PATH",
        "load_memory_baseline",
        "write_self_improvement_artifacts",
    ],
    "scripts/autoresearch_runtime_ctl.py": [
        "--self-improvement-path",
        "--memory-path",
        "Optional reusable memory input path",
        "write_self_improvement_artifacts",
    ],
    "scripts/autoresearch_complete_run.py": [
        "complete_foreground_run",
        "--self-improvement-path",
        "--memory-path",
    ],
    "scripts/autoresearch_wizard.py": [
        "--memory-path",
        "Optional reusable memory input path",
    ],
    "scripts/autoresearch_init_run.py": [
        "--memory-path",
        "Optional reusable memory input path",
    ],
    "scripts/autoresearch_hook_session_start.py": [
        "autoresearch-memory.md",
    ],
}


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert isinstance(payload, dict)
    return payload


def _relative_files(root: Path, pattern: str) -> list[Path]:
    return sorted(path.relative_to(root) for path in root.glob(pattern) if path.is_file())


def _assert_matching_files(source_root: Path, bundled_root: Path, pattern: str) -> None:
    source_files = _relative_files(source_root, pattern)
    bundled_files = _relative_files(bundled_root, pattern)
    assert source_files == bundled_files
    for rel_path in source_files:
        assert (source_root / rel_path).read_bytes() == (bundled_root / rel_path).read_bytes()


def test_plugin_manifest_exists_and_is_valid() -> None:
    payload = _load_json(PLUGIN_MANIFEST)
    assert payload["name"] == "codex-autoresearch"
    assert payload["version"]
    assert payload["skills"] == "./skills/codex-autoresearch"
    interface = payload["interface"]
    assert interface["displayName"]
    assert interface["shortDescription"]
    assert interface["capabilities"]


def test_plugin_skill_payload_is_present() -> None:
    assert PLUGIN_SKILL_ROOT.joinpath("SKILL.md").exists()
    assert PLUGIN_SKILL_ROOT.joinpath("agents", "openai.yaml").exists()


def test_plugin_skill_payload_mirrors_root_sources() -> None:
    assert (REPO_ROOT / "SKILL.md").read_bytes() == PLUGIN_SKILL_ROOT.joinpath("SKILL.md").read_bytes()
    _assert_matching_files(REPO_ROOT / "agents", PLUGIN_SKILL_ROOT / "agents", "*.yaml")
    _assert_matching_files(REPO_ROOT / "scripts", PLUGIN_SKILL_ROOT / "scripts", "*.py")
    _assert_matching_files(REPO_ROOT / "references", PLUGIN_SKILL_ROOT / "references", "*.md")


def test_plugin_self_improvement_workflow_is_mirrored() -> None:
    for rel_path, required_markers in SELF_IMPROVEMENT_PARITY_FILES.items():
        source_path = REPO_ROOT / rel_path
        bundled_path = PLUGIN_SKILL_ROOT / rel_path
        source_text = source_path.read_text(encoding="utf-8")
        bundled_text = bundled_path.read_text(encoding="utf-8")

        assert source_text == bundled_text
        for marker in required_markers:
            assert marker in source_text


def test_plugin_marketplace_entry_points_to_github_source() -> None:
    payload = _load_json(MARKETPLACE_PATH)
    plugins = payload.get("plugins")
    assert isinstance(plugins, list)
    entry = next(
        entry
        for entry in plugins
        if isinstance(entry, dict) and entry.get("name") == "codex-autoresearch"
    )
    source = entry.get("source")
    assert isinstance(source, dict)
    assert source == {
        "source": "github",
        "repo": "Maleick/codex-autoresearch",
        "path": "plugins/codex-autoresearch",
        "ref": "main",
    }


def test_plugin_auxiliary_manifests_are_json_objects() -> None:
    for rel_path in ("hooks.json", ".app.json", ".mcp.json"):
        payload = _load_json(PLUGIN_ROOT / rel_path)
        assert isinstance(payload, dict)


def test_distribution_validator_accepts_repo_snapshot() -> None:
    payload = validate_distribution(REPO_ROOT)

    assert payload["skills_path"].endswith("plugins\\codex-autoresearch\\skills\\codex-autoresearch")
    assert payload["asset_paths"] == {}
    assert "check_plugin_distribution.py" in payload["mirrored"]["scripts"]
