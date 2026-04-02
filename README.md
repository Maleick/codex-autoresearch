# Codex Autoresearch [![GitHub Release](https://img.shields.io/github/v/release/openai/codex-autoresearch?style=flat-square&label=release)](https://github.com/openai/codex-autoresearch/releases) [![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE) [![Language](https://img.shields.io/badge/language-Python-brightgreen?style=flat-square)](plugins/codex-autoresearch) [![Last Commit](https://img.shields.io/github/last-commit/openai/codex-autoresearch?style=flat-square)](https://github.com/openai/codex-autoresearch/commits/main) [![GitHub Stars](https://img.shields.io/github/stars/openai/codex-autoresearch?style=flat-square)](https://github.com/openai/codex-autoresearch/stargazers) [![Repo Size](https://img.shields.io/github/repo-size/openai/codex-autoresearch?style=flat-square)](.) [![Status](https://img.shields.io/badge/status-Active-green?style=flat-square)](CHANGELOG.md) [![Claude Code](https://img.shields.io/badge/compatible-Codex%20Code-blueviolet?style=flat-square)](https://openai.com/product/codex/) [![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-blue?style=flat-square)](.) [![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)](CONTRIBUTING.md)
> **v1.0.0** — [Issues](https://github.com/openai/codex-autoresearch/issues) Autonomous, metric-driven iteration for Codex.

Autonomous, metric-driven iteration for Codex.

This repository is an original implementation inspired by the workflow shape of `leo-lilinxiao/codex-autoresearch`: scan a repo, define a measurable target, make one controlled change, verify it mechanically, keep or discard it, and repeat. The goal here is a smaller and easier-to-understand bundle that still gives Codex a real operating protocol and concrete helper scripts.

It now also includes a guided planning wizard and a compact workflow pack for `plan`, `debug`, `fix`, `learn`, `predict`, `scenario`, `security`, and `ship` style requests, borrowing ideas from `Maleick/claude-autoresearch` without copying that plugin structure directly.

## What This Repo Contains

- `SKILL.md`: the skill entrypoint Codex reads when the bundle is activated
- `agents/openai.yaml`: launcher metadata for Codex-compatible UIs
- `references/`: short protocol documents that keep the loop grounded
- `references/*-workflow.md`: specialized protocols for planning, debugging, fixing, documentation, prediction, scenarios, security, and shipping
- `scripts/`: Python helpers for run setup, iteration logging, and supervisor control
- `tests/`: unit tests for the artifact-management helpers

## Core Ideas

The loop is deliberately simple:

1. Infer a goal and metric from the repo and the user's request.
2. Use the wizard when the setup is incomplete.
3. Confirm missing assumptions before launching a new interactive run.
4. Establish a baseline.
5. Make one focused experiment.
6. Verify progress and run a guard if needed.
7. Retain or discard the experiment.
8. Record what happened.
9. Continue until a stop condition, a blocker, or manual interruption.

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

## Quick Start

Install the skill in a repo-managed location, then activate it in Codex and describe the outcome you want. For example:

```text
$codex-autoresearch
Reduce flaky test failures in the API integration suite.
```

Codex should:

1. Read the repo and generate a setup summary, usually through the wizard when the request is underspecified.
2. Ask for any missing constraints.
3. Ask you to choose `foreground` or `background`.
4. Initialize the run artifacts.
5. Iterate until the goal is met, the run is stopped, or a real blocker appears.

You can also drive the helpers directly:

```text
python scripts/autoresearch_wizard.py --goal "Reduce flaky tests"
python scripts/autoresearch_init_run.py --goal "Reduce flaky tests" --metric "failing tests" --direction lower --verify "pytest tests/integration" --mode foreground --fresh-start
python scripts/autoresearch_record_iteration.py --decision keep --metric-value 7 --change-summary "stabilize API timeout handling"
python scripts/autoresearch_supervisor_status.py
python scripts/autoresearch_runtime_ctl.py complete
python scripts/autoresearch_runtime_ctl.py resume
python scripts/autoresearch_runtime_ctl.py stop
```

## Plugin Packaging

This repository also includes a local plugin artifact at:

- `plugins/codex-autoresearch`
- `plugins/codex-autoresearch/.codex-plugin/plugin.json`
- `plugins/codex-autoresearch/skills/codex-autoresearch/` (bundled skill payload)
- `.agents/plugins/marketplace.json`

To run the plugin-distribution workflow locally:

1. Keep the plugin payload in sync with repository edits that affect skill behavior.
2. Run `git push` after edits; the marketplace entry points at `Maleick/codex-autoresearch`, so updates can come from GitHub.
3. Keep `plugins/codex-autoresearch/.codex-plugin/plugin.json` version updated when making user-facing changes.
4. Keep `marketplace.json` source fields aligned (`ref`/`repo`) if install metadata changes.
5. Add release-ready assets under `plugins/codex-autoresearch/assets` when you want screenshots or icons.

To refresh the installed plugin from GitHub after pushing a new release, re-open or reload Codex so marketplace entries are re-read.

For a fresh plugin creation, use the scaffold script:

```text
python C:/Users/xmale/.codex/skills/.system/plugin-creator/scripts/create_basic_plugin.py codex-autoresearch --with-skills --with-marketplace
```

## Design Differences From The Reference Repo

This version is intentionally narrower than the upstream reference:

- fewer protocol files
- fewer runtime commands (focused on deterministic run-state control)
- smaller helper surface area
- tests focused on artifact semantics instead of end-to-end process orchestration

That keeps the bundle easier to audit and extend while preserving the key behavior: initialize state, log experiments, guide the user through setup, and make deterministic stop-or-continue decisions.
