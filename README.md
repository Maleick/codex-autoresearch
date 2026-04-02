# Codex Autoresearch

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
python scripts/autoresearch_runtime_ctl.py resume
python scripts/autoresearch_runtime_ctl.py stop
```

## Design Differences From The Reference Repo

This version is intentionally narrower than the upstream reference:

- fewer protocol files
- fewer runtime commands
- smaller helper surface area
- tests focused on artifact semantics instead of end-to-end process orchestration

That keeps the bundle easier to audit and extend while preserving the key behavior: initialize state, log experiments, guide the user through setup, and make deterministic stop-or-continue decisions.
