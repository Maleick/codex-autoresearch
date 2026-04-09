# Codex Autoresearch Plugin

This directory contains the plugin-packaged version of `codex-autoresearch` for
GitHub-backed distribution through the Codex plugin marketplace flow, with a
machine-local fallback available only when that path is unavailable.

The packaged docs mirror the root bundle's subagent-first flow: the main agent orchestrates a standing pool of subagents across iterations, while the plan helper, continuation policy, and validation expectations stay aligned with the main README.

What is included:

- `skills/codex-autoresearch/SKILL.md` for runtime invocation instructions.
- `skills/codex-autoresearch/agents/openai.yaml` for UI/launcher metadata.
- `skills/codex-autoresearch/scripts/*` used by the skill workflow.
- `skills/codex-autoresearch/references/*` for scoped protocol and workflow docs.
- `hooks.json`, `.mcp.json`, and `.app.json` as plugin-level manifest targets.

The plugin package is intentionally mirrored from the root repository sources.
Treat the repo root as authoritative for behavior and documentation changes, then run `python3 scripts/sync_plugin_payload.py` before release.
The auxiliary manifest files stay as valid JSON objects even when they are intentionally empty.

## Packaging Notes

- Plugin ID: `codex-autoresearch`
- Marketplace path: `./plugins/codex-autoresearch`
- Manifest: `.codex-plugin/plugin.json`
- Sync: `python3 scripts/sync_plugin_payload.py`
- Validation: `python3 scripts/check_plugin_distribution.py`
- Gate: `python3 scripts/run_contributor_gate.py packaging`

When making changes to the root skill, sync this package, run the distribution checks, and then push to `main` so GitHub-backed installs on multiple machines can pick up the updated packaged payload on reload.
For a single local checkout that should follow `git pull` directly, use `python3 scripts/bootstrap_local_plugin.py --source-mode repo --install-git-hooks` so the local marketplace entry points at this repo bundle and the managed git hooks keep that bundle re-synced after checkout/merge/rewrite operations.
Only add icon, logo, or screenshot fields to `plugin.json` after the referenced asset files exist.
