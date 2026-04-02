from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "codex-autoresearch"
PLUGIN_MANIFEST = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
PLUGIN_SKILL_ROOT = PLUGIN_ROOT / "skills" / "codex-autoresearch"
MARKETPLACE_PATH = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"


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
