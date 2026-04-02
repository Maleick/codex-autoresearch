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
3. For a new interactive run, also read `references/interaction-wizard.md` and `references/loop-workflow.md`.
4. For background control (`status`, `stop`, `resume`, `launch`), use the helper scripts in `scripts/`.
5. Prefer the bundled helpers over manual edits to run artifacts.

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

## Background Control

Use these helpers when managing a detached run:

- `python scripts/autoresearch_runtime_ctl.py launch ...`
- `python scripts/autoresearch_runtime_ctl.py status`
- `python scripts/autoresearch_runtime_ctl.py stop`

Use `python scripts/autoresearch_supervisor_status.py` when a supervisor needs a deterministic relaunch decision.

## Expected Output

Follow `references/structured-output-spec.md`.

At minimum:

- print a setup summary before the first iteration
- show short progress updates during the loop
- finish with a completion or blocker summary

## Notes

This skill bundle does not attempt to prescribe one exact Codex runtime environment. It gives Codex a stable protocol and file format so the interactive workflow and any external runner can share state cleanly.
