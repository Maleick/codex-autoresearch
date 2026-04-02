# Contributing

Contributions should preserve the repo-first packaging model: the repository root is the editable source, and the bundled plugin payload is a mirrored release artifact.

## Source Of Truth

Treat these root paths as authoritative:

- `SKILL.md`
- `agents/`
- `scripts/`
- `references/`

If you change any of them, mirror the corresponding files into `plugins/codex-autoresearch/skills/codex-autoresearch/` before considering the work done.

## Packaging Rules

- Keep `plugins/codex-autoresearch/.codex-plugin/plugin.json` aligned with the current feature surface.
- Keep `.agents/plugins/marketplace.json` pointed at `Maleick/codex-autoresearch`.
- Leave optional icon, logo, or screenshot fields out of `plugin.json` until the referenced files exist.
- Keep `hooks.json`, `.app.json`, and `.mcp.json` as valid JSON objects even when they are intentionally empty.

## Validation

Run these checks before opening a release-oriented change:

```bash
python scripts/check_plugin_distribution.py
python -m pytest
```

The distribution validator checks the packaged plugin payload, mirrored files, and marketplace metadata. The test suite covers helper semantics plus plugin-distribution parity.

## Documentation

When changing the workflow surface or release process, update:

- `README.md`
- `plugins/codex-autoresearch/README.md`
- `CHANGELOG.md` for user-facing release notes

Keep the documentation honest about what is implemented today. Do not advertise plugin assets, workflows, or release steps that are not present in the repository.
