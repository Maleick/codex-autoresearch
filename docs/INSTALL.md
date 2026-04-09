# Installation

`codex-autoresearch` can be used as a repo-managed skill during development or as the packaged plugin payload shipped from this repository.

## Choose An Install Mode

Use the install mode that matches how you want updates to flow:

- Repo-managed skill: best for live development on one machine.
- Repo-tracked local plugin: best when you want the plugin install to follow a local git checkout on one machine.
- GitHub-backed plugin: best when you want the same plugin update path on multiple machines, including macOS and Windows.
- Local fallback plugin: only for machines that cannot install or refresh the GitHub-backed plugin.

## Repo-Managed Skill

Clone the repository and copy or symlink the root folder into your repo-managed skills location:

```bash
git clone https://github.com/Maleick/codex-autoresearch.git
cp -r codex-autoresearch your-project/.agents/skills/codex-autoresearch
```

For live development, prefer a symlink so edits in this repo are reflected immediately:

```bash
git clone https://github.com/Maleick/codex-autoresearch.git
ln -s "$(pwd)/codex-autoresearch" your-project/.agents/skills/codex-autoresearch
```

## Repo-Tracked Local Plugin

If you want the packaged plugin install to follow this checkout directly, bootstrap a local marketplace entry that points at the repo bundle instead of copying a fallback snapshot:

```bash
python3 scripts/bootstrap_local_plugin.py --source-mode repo --install-git-hooks
```

This mode:

- syncs `plugins/codex-autoresearch` from the repo root first
- points the local marketplace entry at this checkout's `plugins/codex-autoresearch`
- installs managed `post-checkout`, `post-merge`, and `post-rewrite` git hooks that re-run `scripts/sync_plugin_payload.py`

Use this mode when `git pull`, branch switches, or rebases should refresh the packaged plugin payload before the next Codex reload. The hook installer refuses to overwrite unmanaged hooks, so existing custom git hooks stay explicit.

## Verify The Skill

Open Codex in the target repo and invoke:

```text
$codex-autoresearch
Reduce flaky test failures in the API integration suite.
```

Expected behavior:

- Codex loads `SKILL.md`
- the wizard summarizes inferred goal, scope, and verification
- Codex asks you to choose `foreground` or `background`

## Optional Session Hooks

For resumed or overnight work, install the managed hooks:

```bash
python scripts/autoresearch_hooks_ctl.py install
python scripts/autoresearch_hooks_ctl.py status
```

These hooks are user-level support files under `$CODEX_HOME`. They help a future session recover the active run context and managed stop behavior.

## Plugin Payload

The packaged plugin lives under `plugins/codex-autoresearch`. The repository root remains the authoring source of truth:

- `SKILL.md`
- `agents/`
- `scripts/`
- `references/`

When maintaining the GitHub-backed plugin payload, use this workflow:

1. Edit the root source-of-truth files.
2. Run `python3 scripts/sync_plugin_payload.py`.
3. Run the plugin payload validation checks.
4. Push to `main`.

GitHub-backed installs resolve `plugins/codex-autoresearch` from `Maleick/codex-autoresearch@main`, so plugin consumers get the packaged payload you pushed after they reload Codex.

For a multi-machine setup, make the Codex marketplace on each machine point at the GitHub source instead of a machine-local `./plugins/...` source:

```json
{
  "name": "codex-autoresearch",
  "interface": {
    "displayName": "Autoresearch Plugins"
  },
  "plugins": [
    {
      "name": "codex-autoresearch",
      "source": {
        "source": "github",
        "repo": "Maleick/codex-autoresearch",
        "path": "plugins/codex-autoresearch",
        "ref": "main"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

With that marketplace name, enable `codex-autoresearch@codex-autoresearch` in `~/.codex/config.toml` on each machine, then reload Codex.

For machine-local fallback setup when Codex cannot refresh GitHub-backed plugins, see [docs/LOCAL-FALLBACK-BOOTSTRAP.md](LOCAL-FALLBACK-BOOTSTRAP.md).

## Release Validation

Before shipping the plugin payload, run:

```bash
python3 scripts/run_contributor_gate.py packaging
```

That gate runs `sync_plugin_payload.py --check`, `check_plugin_distribution.py`, and the plugin-distribution pytest suite together. For behavior-changing work, prefer `python3 scripts/run_contributor_gate.py skill`, which also runs the full pytest suite and a temporary background-control smoke test. GitHub Actions reruns the same contributor gate on pushes and pull requests. Leave icon/logo/screenshot fields out of the plugin manifest until the referenced files actually exist under `plugins/codex-autoresearch/assets`.
