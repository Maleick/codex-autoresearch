---
name: codex-autoresearch
description: "Run a structured improve-verify loop in Codex. Use this when the user wants an autonomous or semi-autonomous iteration cycle toward a measurable goal, including repeated debugging, cleanup, hardening, or release-readiness work."
metadata:
  short-description: "Run a structured autoresearch loop"
---

# codex-autoresearch

Use this skill when the task is larger than a one-shot edit and benefits from repeated experiments with mechanical verification.

## Activation Contract

When the skill is invoked:

1. Read `references/core-principles.md`.
2. Read `references/structured-output-spec.md`.
3. For a new interactive run, also read `references/interaction-wizard.md`, `references/plan-workflow.md`, and `references/loop-workflow.md`.
4. For state and results semantics, also read `references/state-management.md` and `references/results-logging.md`.
5. If the user asks for a specialized mode, also read the matching workflow reference:
   - `references/debug-workflow.md`
   - `references/fix-workflow.md`
   - `references/learn-workflow.md`
   - `references/predict-workflow.md`
   - `references/scenario-workflow.md`
   - `references/security-workflow.md`
   - `references/ship-workflow.md`
6. For background control (`status`, `stop`, `resume`, `launch`), use the helper scripts in `scripts/`.
7. Prefer the bundled helpers over manual edits to run artifacts.

## Required Internal Fields

Infer or confirm these before launching a new run:

- `Goal`
- `Scope`
- `Metric`
- `Direction`
- `Verify`

Strongly recommended:

- `Guard`
- `Run Mode` (`foreground` or `background`)
- `Iteration Cap`
- `Stop Condition`
- `Rollback Strategy`

## Execution Rules

1. Always read the relevant in-scope files before the first write of a new run.
2. Ask at least one repo-grounded clarification round for a new interactive launch.
3. Require an explicit `foreground` or `background` choice before starting.
4. Baseline exactly once at run start.
5. Make one focused experiment per iteration.
6. Verify mechanically. Do not retain a change on intuition alone.
7. Record every completed iteration before the next one starts.
8. Do not revert unrelated user work.
9. Treat run artifacts as generated working state, not source files to commit.
10. If the run gets stuck, change strategy instead of brute-forcing the same idea.

## Mode Routing

Use the default loop for metric-driven optimization.

Use specialized workflows when the user asks to plan, debug, fix, learn, predict, expand scenarios, run a security pass, or prepare to ship.

For planning, prefer `python scripts/autoresearch_wizard.py` to generate the initial setup summary before asking the user the remaining questions.

## Background Control

Use these helpers when managing a detached run:

- `python scripts/autoresearch_runtime_ctl.py launch ...`
- `python scripts/autoresearch_runtime_ctl.py status`
- `python scripts/autoresearch_runtime_ctl.py stop`
- `python scripts/autoresearch_runtime_ctl.py resume`

Use `python scripts/autoresearch_supervisor_status.py` when a supervisor needs a deterministic relaunch decision.

## Expected Output

Follow `references/structured-output-spec.md`.

At minimum:

- print a setup summary before the first iteration
- show short progress updates during the loop
- finish with a completion or blocker summary

## Notes

This skill bundle does not attempt to prescribe one exact Codex runtime environment. It gives Codex a stable protocol and file format so the interactive workflow and any external runner can share state cleanly.
