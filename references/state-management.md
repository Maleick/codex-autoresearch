# State Management

`autoresearch-state.json` is the run checkpoint.

## Core Fields

- `run_id`: stable identifier for the current run
- `status`: `initialized`, `running`, `stopping`, `stopped`, or `completed`
- `mode`: `foreground` or `background`
- `goal`: human-readable objective
- `metric`: name, direction, baseline, latest, and best values
- `stats`: total iterations, keep/discard counters, best iteration, and discard streak
- `flags`: stop request, needs-human marker, and background activity
- `last_iteration`: summary of the latest completed iteration

## Rules

1. Baseline exactly once when the run is initialized.
2. Update `updated_at` on every state mutation.
3. Keep `metric.latest` aligned with the most recent finished iteration.
4. Only update `metric.best` on strict improvement.
5. Set `flags.needs_human=true` when autonomous progress should stop for user input.
6. For detached runs, `flags.background_active` reflects whether a background owner is currently expected to continue the loop.

## Resume Semantics

- `python scripts/autoresearch_runtime_ctl.py resume` clears `stop_requested` and marks the background run active again.
- Resume does not create a new run; it continues the existing state snapshot.
- If the run is not a background run, resume should fail fast.
