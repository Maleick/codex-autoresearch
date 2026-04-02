# Codex Autoresearch Plugin

This directory contains the plugin-packaged version of `codex-autoresearch` for
local distribution through the Codex plugin marketplace flow.

What is included:

- `skills/codex-autoresearch/SKILL.md` for runtime invocation instructions.
- `skills/codex-autoresearch/agents/openai.yaml` for UI/launcher metadata.
- `skills/codex-autoresearch/scripts/*` used by the skill workflow.
- `skills/codex-autoresearch/references/*` for scoped protocol and workflow docs.

The plugin package is intentionally mirrored from the root repository sources.
Treat the repo root as authoritative for behavior and documentation changes, then sync this bundled payload before release.

## Packaging Notes

- Plugin ID: `codex-autoresearch`
- Marketplace path: `./plugins/codex-autoresearch`
- Manifest: `.codex-plugin/plugin.json`

When making changes to the root skill, mirror required resource updates in this
plugin package so plugin consumers keep a complete feature set.
