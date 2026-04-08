# Codex Autoresearch [![GitHub Release](https://img.shields.io/github/v/release/Maleick/codex-autoresearch?style=flat-square&label=release)](https://github.com/Maleick/codex-autoresearch/releases) [![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE) [![Language](https://img.shields.io/badge/language-Python-brightgreen?style=flat-square)](plugins/codex-autoresearch) [![Last Commit](https://img.shields.io/github/last-commit/Maleick/codex-autoresearch?style=flat-square)](https://github.com/Maleick/codex-autoresearch/commits/main) [![GitHub Stars](https://img.shields.io/github/stars/Maleick/codex-autoresearch?style=flat-square)](https://github.com/Maleick/codex-autoresearch/stargazers) [![Repo Size](https://img.shields.io/github/repo-size/Maleick/codex-autoresearch?style=flat-square)](.) [![Status](https://img.shields.io/badge/status-Active-green?style=flat-square)](CHANGELOG.md) [![Claude Code](https://img.shields.io/badge/compatible-Codex%20Code-blueviolet?style=flat-square)](https://openai.com/product/codex/) [![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-blue?style=flat-square)](.) [![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)](CONTRIBUTING.md)
> **v1.1.1** - [Issues](https://github.com/Maleick/codex-autoresearch/issues) Subagent-first, metric-driven iteration for Codex.

Subagent-first, metric-driven iteration for Codex.

This repository is an original implementation inspired by the workflow shape of `leo-lilinxiao/codex-autoresearch`: scan a repo, define a measurable target, make one controlled change, verify it mechanically, keep or discard it, and repeat. The goal here is a smaller and easier-to-understand bundle that still gives Codex a real operating protocol and concrete helper scripts.

It now also includes a plan helper, expressed here as a guided planning wizard, a standing subagent-pool contract, and a compact workflow pack for `plan`, `debug`, `fix`, `learn`, `predict`, `scenario`, `security`, and `ship` style requests, borrowing ideas from `Maleick/claude-autoresearch` without copying that plugin structure directly.

Autoresearch is subagent-first: the main agent stays in the orchestrator role, keeps a standing pool of subagents available across iterations, delegates focused work, folds the results back into the loop, and keeps running after launch until you stop it, the configured stop condition is met, or a real blocker requires human input.

Compared with `leo-lilinxiao/codex-autoresearch` and `Maleick/claude-autoresearch`, this repo supports explicit wall-clock caps for unattended runs, so an overnight plan can be bounded by both iterations and elapsed time.
The bundle also includes managed session hooks, a foreground completion helper, automatic memory carry-forward into the next run, and a dedicated plugin-distribution validator for the packaged Codex plugin.

## What This Repo Contains

- `SKILL.md`: the skill entrypoint Codex reads when the bundle is activated
- `agents/openai.yaml`: launcher metadata for Codex-compatible UIs
- `references/`: short protocol documents that keep the loop grounded
- `references/runtime-hard-invariants.md`: a short re-anchor checklist for resumed or long-running runs
- `references/*-workflow.md`: specialized protocols for planning, debugging, fixing, documentation, prediction, scenarios, security, and shipping
- `scripts/`: Python helpers for run setup, iteration logging, completion, hook installation, plugin payload sync and validation, supervisor control, and contributor gates
- `tests/`: unit tests for artifact semantics, hooks, skill contracts, contributor gates, and plugin-distribution coverage

## Core Ideas

The loop is deliberately simple:

1. Infer a goal and metric from the repo and the user's request.
2. Use the wizard when the setup is incomplete and summarize the standing pool plan.
3. Confirm missing assumptions before launching a new interactive run.
4. Establish a baseline.
5. Re-anchor the standing subagent pool around the current goal, scope, and latest result.
6. Make one focused experiment.
7. Verify progress and run a guard if needed.
8. Retain or discard the experiment.
9. Record what happened.
10. Continue until a stop condition, a blocker, or manual interruption.

Foreground and background runs share the same artifacts. The difference is where the loop executes:

- `foreground`: the current Codex session owns the loop
- `background`: a detached runner owns the loop, while the current session only controls manifests and status

## Feature Surface

The main loop remains the center of the bundle, but the skill can now route into these narrower workflows when the user asks for them:

- `plan`: interactive setup and run-shaping
- `debug`: evidence-first investigation before repair
- `fix`: bounded error-repair loop
- `learn`: documentation and codebase understanding
- `predict`: multi-angle risk and tradeoff analysis
- `scenario`: edge-case and use-case generation
- `security`: structured security review
- `ship`: release-readiness and closeout

## Artifact Files

By default the scripts manage these repo-root files:

- `autoresearch-state.json`
- `research-results.tsv`
- `autoresearch-launch.json`

These are intentionally uncommitted working artifacts. The helper scripts can also archive a previous run to `*.prev.*` when you request a fresh start.
Operator handoff notes and local scratch files should stay outside the published repo surface and live in ignored local files such as `HANDOFF*.md`.

For unattended runs, the bundle can also produce:

- `autoresearch-report.md`
- `autoresearch-self-improvement.md`
- `autoresearch-memory.md`
- `autoresearch-hook-context.json`

## Quick Start

Install the skill in a repo-managed location for live development, or install the packaged plugin from GitHub if you want one update path shared across multiple Codex machines. For example:

```text
$codex-autoresearch
Reduce flaky test failures in the API integration suite.
```

Codex should:

1. Read the repo and generate a setup summary, usually through the wizard when the request is underspecified.
2. Ask for any missing constraints.
3. Ask you to choose `foreground` or `background`.
4. Initialize the run artifacts and the standing subagent pool plan.
5. Keep the main agent as orchestrator while reusing the same worker pool across iterations.
6. Iterate until the goal is met, the run is stopped, or a real blocker appears.

Continuation is simple on purpose: `autoresearch-memory.md` carries context forward, `resume` and `stop` manage the next step, and the per-iteration `--verify` command plus the contributor gate keep validation mechanical.

You can also drive the helpers directly:

```text
python scripts/autoresearch_wizard.py --goal "Reduce flaky tests overnight" --mode background --iterations 50 --duration 5h
python scripts/autoresearch_subagent_plan.py --goal "Reduce flaky tests overnight" --scope api/tests --mode background
python scripts/autoresearch_wizard.py --goal "Reduce flaky tests overnight" --mode background --iterations 50 --duration 5h --required-keep-labels verified --required-stop-labels ship-ready
python scripts/autoresearch_init_run.py --goal "Reduce flaky tests" --metric "failing tests" --direction lower --verify "pytest tests/integration" --mode foreground --fresh-start
python scripts/autoresearch_init_run.py --goal "Continue last autoresearch loop" --metric "failing tests" --direction lower --verify "pytest tests/integration" --mode foreground --memory-path autoresearch-memory.md --fresh-start
python scripts/autoresearch_record_iteration.py --decision keep --metric-value 7 --change-summary "stabilize API timeout handling"
python scripts/autoresearch_runtime_ctl.py launch --goal "Reduce flaky tests overnight" --metric "failing tests" --direction lower --verify "pytest tests/integration" --iterations 50 --duration 5h --required-keep-labels verified --required-stop-labels ship-ready --dry-run
python scripts/autoresearch_runtime_ctl.py launch --goal "Continue last autoresearch loop overnight" --metric "failing tests" --direction lower --verify "pytest tests/integration" --iterations 50 --duration 5h --memory-path autoresearch-memory.md --dry-run
python scripts/autoresearch_runtime_ctl.py launch --goal "Reduce flaky tests overnight" --metric "failing tests" --direction lower --verify "pytest tests/integration" --iterations 50 --duration 5h --fresh-start
python scripts/autoresearch_runtime_ctl.py status --report-path autoresearch-report.md
python scripts/autoresearch_supervisor_status.py
python scripts/autoresearch_complete_run.py
python scripts/autoresearch_runtime_ctl.py complete
python scripts/autoresearch_runtime_ctl.py resume
python scripts/autoresearch_runtime_ctl.py stop
```

For overnight runs, set both `--iterations` and `--duration`. For example, `--iterations 50 --duration 5h` lets the run stop on either the iteration cap or the time budget.
If you want hard retention/stop gates, pair that with `--required-keep-labels` and `--required-stop-labels`.
Every completed run now also writes `autoresearch-self-improvement.md` and `autoresearch-memory.md`. The next wizard, init, and background launch flow automatically load `autoresearch-memory.md` when it exists, unless you deliberately override it with `--memory-path`.
Setup summaries, state artifacts, launch manifests, and status snapshots now also carry a `subagent_pool` plan plus a `continuation_policy`, so resumed runs can keep the same orchestrator-first structure instead of rethinking the pool from scratch.
For copy/symlink installation details and the release-validation commands, see [docs/INSTALL.md](docs/INSTALL.md).
Use `scripts/autoresearch_complete_run.py` for foreground runs. `scripts/autoresearch_runtime_ctl.py complete` remains the background-run completion path.
For machine-local fallback setup when Codex cannot refresh GitHub-backed plugins, see [docs/LOCAL-FALLBACK-BOOTSTRAP.md](docs/LOCAL-FALLBACK-BOOTSTRAP.md).

## Session Hooks

For resumed or overnight work, you can install user-level Codex hooks that remind a future session about an active run and block premature stop when the supervisor still wants to relaunch:

```text
python scripts/autoresearch_hooks_ctl.py install
python scripts/autoresearch_hooks_ctl.py status
python scripts/autoresearch_hooks_ctl.py uninstall
```

The hook installer writes under `$CODEX_HOME` and keeps a manifest so it can remove only the managed hook entries later.
Those same hook and context files are mirrored into the packaged plugin payload so marketplace installs preserve the same resumed-session behavior.

## Contributor Gate

For maintainers, the repo now includes a single entrypoint for self-checks:

```text
python3 scripts/run_contributor_gate.py packaging
python3 scripts/run_contributor_gate.py skill
```

`packaging` runs the sync check, distribution validator, and plugin-distribution tests.
`skill` runs those checks, the full pytest suite, and a temporary background-control smoke test that exercises `launch`, `status`, `stop`, `resume`, and `complete`.

## Plugin Packaging

This repository also includes a local plugin artifact at:

- `plugins/codex-autoresearch`
- `plugins/codex-autoresearch/.codex-plugin/plugin.json`
- `plugins/codex-autoresearch/skills/codex-autoresearch/` (bundled skill payload)
- `.agents/plugins/marketplace.json`

To update the GitHub-backed plugin safely:

1. Treat the repo root (`SKILL.md`, `agents/`, `scripts/`, and `references/`) as the source of truth.
2. Run `python3 scripts/sync_plugin_payload.py` to mirror root-source changes into `plugins/codex-autoresearch/skills/codex-autoresearch/`.
3. Keep `plugins/codex-autoresearch/.codex-plugin/plugin.json` version updated when making user-facing plugin changes.
4. Update `CHANGELOG.md` with release notes before tagging a user-facing release.
5. Keep `.agents/plugins/marketplace.json` source fields aligned (`ref`/`repo`) if install metadata changes.
6. Run `python3 scripts/run_contributor_gate.py packaging` or the equivalent underlying checks.
7. Push to `main`; the marketplace entry points at `Maleick/codex-autoresearch`, so GitHub-backed installs will pick up the packaged plugin after Codex reloads.
8. CI reruns the contributor gate on pushes and pull requests.
9. Add release-ready assets under `plugins/codex-autoresearch/assets` only when you also wire those files into `plugin.json`.

For shared Mac and Windows installs, prefer the GitHub-backed marketplace entry over the machine-local fallback so both machines resolve the same packaged payload from `Maleick/codex-autoresearch@main`.
To refresh the installed plugin from GitHub after pushing a new release, re-open or reload Codex so marketplace entries are re-read.
If a specific machine cannot install the GitHub-backed plugin directly, run `python3 scripts/bootstrap_local_plugin.py` to populate the supported machine-local fallback under `~/plugins`; see [docs/LOCAL-FALLBACK-BOOTSTRAP.md](docs/LOCAL-FALLBACK-BOOTSTRAP.md).
Contributor-facing packaging rules live in [CONTRIBUTING.md](CONTRIBUTING.md).
The plugin marketplace card text is sourced from `plugins/codex-autoresearch/.codex-plugin/plugin.json`, so keep that interface metadata aligned with the current README language when cutting a release.

## Design Differences From The Reference Repo

This version is intentionally narrower than the upstream reference:

- fewer protocol files
- fewer runtime commands (focused on deterministic run-state control)
- smaller helper surface area
- lighter-weight contributor/runtime validation instead of full end-to-end orchestration

That keeps the bundle easier to audit and extend while preserving the key behavior: initialize state, log experiments, guide the user through setup, and make deterministic stop-or-continue decisions.
