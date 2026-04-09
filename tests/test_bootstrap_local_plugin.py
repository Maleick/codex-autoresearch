from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.bootstrap_local_plugin import (
    DEFAULT_MARKETPLACE_DISPLAY_NAME,
    DEFAULT_MARKETPLACE_NAME,
    GIT_SYNC_HOOK_NAMES,
    MANAGED_HOOK_SENTINEL,
    PLUGIN_NAME,
    SOURCE_MODE_REPO,
    BootstrapError,
    bootstrap_local_plugin,
    build_local_plugin_entry,
    install_git_sync_hooks,
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


def _git_init(repo_root: Path) -> None:
    subprocess.run(
        ["git", "init"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def test_build_local_plugin_entry_rewrites_repo_source_to_local_path(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _make_repo(repo_root)

    entry = build_local_plugin_entry(
        load_repo_marketplace_entry(repo_root),
        home_root=tmp_path / "home",
        plugin_root=tmp_path / "home" / "plugins" / PLUGIN_NAME,
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
            plugin_root=tmp_path / "elsewhere" / PLUGIN_NAME,
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
                plugin_root=install_root / PLUGIN_NAME,
            ),
            marketplace_name=DEFAULT_MARKETPLACE_NAME,
            marketplace_display_name=DEFAULT_MARKETPLACE_DISPLAY_NAME,
        )


def test_bootstrap_local_plugin_repo_mode_tracks_repo_bundle(tmp_path: Path) -> None:
    home_root = tmp_path / "home"
    repo_root = home_root / "Projects" / "codex-autoresearch"
    plugin_root = _make_repo(repo_root)
    install_root = home_root / "plugins"
    marketplace_path = home_root / ".agents" / "plugins" / "marketplace.json"

    result = bootstrap_local_plugin(
        repo_root,
        install_root=install_root,
        marketplace_path=marketplace_path,
        marketplace_name=DEFAULT_MARKETPLACE_NAME,
        marketplace_display_name=DEFAULT_MARKETPLACE_DISPLAY_NAME,
        sync_source=False,
        source_mode=SOURCE_MODE_REPO,
    )

    payload = _load_json(marketplace_path)
    assert payload["plugins"][0]["source"] == {
        "source": "local",
        "path": "./Projects/codex-autoresearch/plugins/codex-autoresearch",
    }
    assert result["install_target"] == str(plugin_root)
    assert result["source_mode"] == SOURCE_MODE_REPO
    assert result["source_action"] == "tracked"


def test_install_git_sync_hooks_creates_managed_hooks(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    _git_init(repo_root)

    result = install_git_sync_hooks(repo_root)
    hooks_root = Path(result["hooks_root"])
    runner_path = hooks_root / "codex-autoresearch-sync"

    assert runner_path.exists()
    assert "sync_plugin_payload.py" in runner_path.read_text(encoding="utf-8")
    for hook_name in GIT_SYNC_HOOK_NAMES:
        hook_path = hooks_root / hook_name
        assert hook_path.exists()
        assert MANAGED_HOOK_SENTINEL in hook_path.read_text(encoding="utf-8")


def test_install_git_sync_hooks_refuses_to_overwrite_unmanaged_hook(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    _git_init(repo_root)
    hooks_root = repo_root / ".git" / "hooks"
    hook_path = hooks_root / "post-merge"
    hook_path.write_text("#!/bin/sh\necho unmanaged\n", encoding="utf-8")

    with pytest.raises(BootstrapError, match="unmanaged git hook"):
        install_git_sync_hooks(repo_root)
