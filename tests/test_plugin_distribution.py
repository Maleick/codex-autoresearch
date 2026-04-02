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


def test_plugin_marketplace_entry_points_to_local_path() -> None:
    payload = _load_json(MARKETPLACE_PATH)
    plugins = payload.get("plugins")
    assert isinstance(plugins, list)
    assert any(
        entry.get("source", {}).get("path") == "./plugins/codex-autoresearch"
        for entry in plugins
        if isinstance(entry, dict)
    )

