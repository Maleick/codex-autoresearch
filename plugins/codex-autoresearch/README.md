# Codex Autoresearch Plugin

This directory contains the plugin-packaged version of `codex-autoresearch` for
local distribution through the Codex plugin marketplace flow.

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

When making changes to the root skill, sync this package, run the distribution checks, and then push to `main` so GitHub-backed installs can pick up the updated packaged payload on reload.
Only add icon, logo, or screenshot fields to `plugin.json` after the referenced asset files exist.
