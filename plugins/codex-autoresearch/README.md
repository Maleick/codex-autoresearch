# Codex Autoresearch Plugin

This directory contains the plugin-packaged version of `codex-autoresearch` for
local distribution through the Codex plugin marketplace flow.

What is included:

- `SKILL.md` for runtime invocation instructions.
- `agents/openai.yaml` for UI/launcher metadata.
- `scripts/*` used by the skill workflow.
- `references/*` for scoped protocol and workflow docs.

The plugin package is intentionally kept in sync with the root repository sources.

## Packaging Notes

- Plugin ID: `codex-autoresearch`
- Marketplace path: `./plugins/codex-autoresearch`
- Manifest: `.codex-plugin/plugin.json`

When making changes to the root skill, mirror required resource updates in this
plugin package so plugin consumers keep a complete feature set.

