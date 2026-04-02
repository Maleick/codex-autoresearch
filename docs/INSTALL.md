# Installation

`codex-autoresearch` can be used as a repo-managed skill during development or as the packaged plugin payload shipped from this repository.

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

For machine-local fallback setup when Codex cannot refresh GitHub-backed plugins, see [docs/LOCAL-FALLBACK-BOOTSTRAP.md](LOCAL-FALLBACK-BOOTSTRAP.md).

## Release Validation

Before shipping the plugin payload, run:

```bash
python3 scripts/sync_plugin_payload.py --check
python3 scripts/check_plugin_distribution.py
python3 -m pytest tests/test_plugin_distribution.py
```

`sync_plugin_payload.py --check` fails when the packaged plugin drifts from the root source. `check_plugin_distribution.py` verifies root-to-plugin parity, auxiliary manifest validity, and marketplace metadata. GitHub Actions reruns the same checks on pushes and pull requests. Leave icon/logo/screenshot fields out of the plugin manifest until the referenced files actually exist under `plugins/codex-autoresearch/assets`.
