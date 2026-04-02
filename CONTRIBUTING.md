# Contributing

Contributions should preserve the repo-first packaging model: the repository root is the editable source, and the bundled plugin payload is a mirrored release artifact.

## Source Of Truth

Treat these root paths as authoritative:

- `SKILL.md`
- `agents/`
- `scripts/`
- `references/`

If you change any of them, mirror the corresponding files into `plugins/codex-autoresearch/skills/codex-autoresearch/` before considering the work done.

## Subagent-First Skill Contract

When you change the skill contract or the contributor expectations around it, make the lightweight contract test and verification surfaces part of the same patch:

1. Update `tests/test_skill_contract.py` first so the new expectation is mechanically checked.
2. Record the work in `feature-list.json` so the contract change is tracked across sessions.
3. Keep the relevant doc language explicit about the subagent-first skill contract instead of relying on implied process.
4. Mirror any root source changes into `plugins/codex-autoresearch/skills/codex-autoresearch/` before handing the work off.

## Edit To Release Workflow

Use this sequence whenever you want GitHub-backed plugin installs to pick up your changes:

1. Edit the root source-of-truth files.
2. Run `python3 scripts/sync_plugin_payload.py`.
3. Update `plugins/codex-autoresearch/.codex-plugin/plugin.json` when the plugin's user-facing metadata changes.
4. Update `CHANGELOG.md` for user-facing releases.
5. Run the appropriate contributor gate.
6. Push to `main`.

GitHub-backed installs resolve `plugins/codex-autoresearch` from `main`, so plugin consumers get the packaged payload you pushed after they reload Codex.

## Packaging Rules

- Keep `plugins/codex-autoresearch/.codex-plugin/plugin.json` aligned with the current feature surface.
- Keep `.agents/plugins/marketplace.json` pointed at `Maleick/codex-autoresearch`.
- Leave optional icon, logo, or screenshot fields out of `plugin.json` until the referenced files exist.
- Keep `hooks.json`, `.app.json`, and `.mcp.json` as valid JSON objects even when they are intentionally empty.

## Validation

Use the contributor gate that matches the scope of your change:

```bash
python3 scripts/run_contributor_gate.py packaging
python3 scripts/run_contributor_gate.py skill
```

`packaging` is the lighter release-oriented gate: sync check, distribution validator, and plugin-distribution tests.
`skill` adds the full pytest suite plus a temporary background-control smoke test that exercises `launch`, `status`, `stop`, `resume`, and `complete`.

If you need the individual commands, the contributor gate is composed from:

```bash
python3 scripts/sync_plugin_payload.py --check
python3 scripts/check_plugin_distribution.py
python3 -m pytest tests/test_plugin_distribution.py
python3 -m pytest -q
```

GitHub Actions reruns the same contributor gate on pushes and pull requests.

## Documentation

When changing the workflow surface or release process, update:

- `README.md`
- `plugins/codex-autoresearch/README.md`
- `CHANGELOG.md` for user-facing release notes

Keep those docs aligned on the subagent-first model, the plan helper, continuation behavior, and validation expectations.

## Subagent-First Contract

When you change the standing-pool behavior, keep these surfaces aligned:

- `SKILL.md`
- `agents/openai.yaml`
- `references/subagent-orchestration.md`
- `references/interaction-wizard.md`
- `references/loop-workflow.md`
- `plugins/codex-autoresearch/.codex-plugin/plugin.json`
- `tests/test_autoresearch_helpers.py`
- `tests/test_autoresearch_hooks.py`
- `tests/test_skill_contract.py`
- `feature-list.json`

Keep the documentation honest about what is implemented today. Do not advertise plugin assets, workflows, or release steps that are not present in the repository.
