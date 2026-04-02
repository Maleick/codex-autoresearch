from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.bootstrap_local_plugin import (
    DEFAULT_MARKETPLACE_DISPLAY_NAME,
    DEFAULT_MARKETPLACE_NAME,
    PLUGIN_NAME,
    BootstrapError,
    bootstrap_local_plugin,
    build_local_plugin_entry,
    load_repo_marketplace_entry,
    merge_marketplace_entry,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative_files(root: Path) -> list[Path]:
    return sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())


def _assert_matching_trees(source_root: Path, target_root: Path) -> None:
    source_files = _relative_files(source_root)
    target_files = _relative_files(target_root)
    assert source_files == target_files
    for rel_path in source_files:
        assert (source_root / rel_path).read_bytes() == (target_root / rel_path).read_bytes()


def _make_repo(repo_root: Path) -> Path:
    plugin_root = repo_root / "plugins" / PLUGIN_NAME
    skill_root = plugin_root / "skills" / PLUGIN_NAME
    mirrored_script = skill_root / "scripts" / "helper.py"

    (plugin_root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    mirrored_script.parent.mkdir(parents=True, exist_ok=True)
    _write_json(
        plugin_root / ".codex-plugin" / "plugin.json",
        {
            "name": PLUGIN_NAME,
            "version": "1.0.3",
            "skills": f"./skills/{PLUGIN_NAME}",
            "hooks": "./hooks.json",
            "mcpServers": "./.mcp.json",
            "apps": "./.app.json",
            "interface": {
                "displayName": "Autoresearch",
                "shortDescription": "Run measurable foreground or background improve-verify loops.",
            },
        },
    )
    _write_json(plugin_root / "hooks.json", {})
    _write_json(plugin_root / ".mcp.json", {})
    _write_json(plugin_root / ".app.json", {})
    (skill_root / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
    mirrored_script.write_text("VALUE = 1\n", encoding="utf-8")

    _write_json(
        repo_root / ".agents" / "plugins" / "marketplace.json",
        {
            "name": PLUGIN_NAME,
            "interface": {"displayName": "Autoresearch Plugins"},
            "plugins": [
                {
                    "name": PLUGIN_NAME,
                    "source": {
                        "source": "github",
                        "repo": "Maleick/codex-autoresearch",
                        "path": "plugins/codex-autoresearch",
                        "ref": "main",
                    },
                    "policy": {
                        "installation": "AVAILABLE",
                        "authentication": "ON_INSTALL",
                    },
                    "category": "Productivity",
                }
            ],
        },
    )
    return plugin_root


def test_build_local_plugin_entry_rewrites_repo_source_to_local_path(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _make_repo(repo_root)

    entry = build_local_plugin_entry(
        load_repo_marketplace_entry(repo_root),
        home_root=tmp_path / "home",
        install_root=tmp_path / "home" / "plugins",
    )

    assert entry["source"] == {
        "source": "local",
        "path": "./plugins/codex-autoresearch",
    }
    assert entry["policy"]["installation"] == "AVAILABLE"
    assert entry["category"] == "Productivity"


def test_bootstrap_local_plugin_copies_bundle_and_creates_marketplace(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    plugin_root = _make_repo(repo_root)
    install_root = tmp_path / "home" / "plugins"
    marketplace_path = tmp_path / "home" / ".agents" / "plugins" / "marketplace.json"

    result = bootstrap_local_plugin(
        repo_root,
        install_root=install_root,
        marketplace_path=marketplace_path,
        marketplace_name=DEFAULT_MARKETPLACE_NAME,
        marketplace_display_name=DEFAULT_MARKETPLACE_DISPLAY_NAME,
        sync_source=False,
    )

    install_target = install_root / PLUGIN_NAME
    _assert_matching_trees(plugin_root, install_target)
    payload = _load_json(marketplace_path)
    assert payload["name"] == DEFAULT_MARKETPLACE_NAME
    assert payload["interface"]["displayName"] == DEFAULT_MARKETPLACE_DISPLAY_NAME
    assert payload["plugins"][0]["name"] == PLUGIN_NAME
    assert payload["plugins"][0]["source"] == {
        "source": "local",
        "path": "./plugins/codex-autoresearch",
    }
    assert result["plugin_reference"] == f"{PLUGIN_NAME}@{DEFAULT_MARKETPLACE_NAME}"
    assert result["source_path"] == "./plugins/codex-autoresearch"


def test_bootstrap_local_plugin_preserves_marketplace_name_and_other_plugins(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    _make_repo(repo_root)
    install_root = tmp_path / "home" / "plugins"
    marketplace_path = tmp_path / "home" / ".agents" / "plugins" / "marketplace.json"
    _write_json(
        marketplace_path,
        {
            "name": "team-marketplace",
            "interface": {"displayName": "Team Marketplace"},
            "plugins": [
                {
                    "name": "github",
                    "source": {"source": "local", "path": "./plugins/github"},
                    "policy": {"installation": "AVAILABLE"},
                    "category": "Developer Tools",
                }
            ],
        },
    )

    result = bootstrap_local_plugin(
        repo_root,
        install_root=install_root,
        marketplace_path=marketplace_path,
        marketplace_name=DEFAULT_MARKETPLACE_NAME,
        marketplace_display_name=DEFAULT_MARKETPLACE_DISPLAY_NAME,
        sync_source=False,
    )

    payload = _load_json(marketplace_path)
    assert payload["name"] == "team-marketplace"
    assert payload["plugins"][0]["name"] == "github"
    assert payload["plugins"][1]["source"] == {
        "source": "local",
        "path": "./plugins/codex-autoresearch",
    }
    assert result["plugin_reference"] == f"{PLUGIN_NAME}@team-marketplace"


def test_build_local_plugin_entry_rejects_install_outside_home(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _make_repo(repo_root)

    with pytest.raises(BootstrapError):
        build_local_plugin_entry(
            load_repo_marketplace_entry(repo_root),
            home_root=tmp_path / "home",
            install_root=tmp_path / "elsewhere",
        )


def test_merge_marketplace_entry_rejects_non_local_unrelated_plugins(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _make_repo(repo_root)
    home_root = tmp_path / "home"
    install_root = home_root / "plugins"
    marketplace_path = home_root / ".agents" / "plugins" / "marketplace.json"
    _write_json(
        marketplace_path,
        {
            "name": DEFAULT_MARKETPLACE_NAME,
            "interface": {"displayName": DEFAULT_MARKETPLACE_DISPLAY_NAME},
            "plugins": [
                {
                    "name": "github",
                    "source": {"source": "github", "repo": "openai/github-plugin"},
                    "policy": {"installation": "AVAILABLE"},
                    "category": "Developer Tools",
                }
            ],
        },
    )

    with pytest.raises(BootstrapError, match="source='local'"):
        merge_marketplace_entry(
            marketplace_path,
            build_local_plugin_entry(
                load_repo_marketplace_entry(repo_root),
                home_root=home_root,
                install_root=install_root,
            ),
            marketplace_name=DEFAULT_MARKETPLACE_NAME,
            marketplace_display_name=DEFAULT_MARKETPLACE_DISPLAY_NAME,
        )
