# Loop Workflow

## Phase 1: Setup

1. Read the relevant code and repo configuration.
2. Generate the initial setup summary with `scripts/autoresearch_wizard.py` when the request is incomplete.
3. Summarize the goal, scope, metric, direction, verify command, and guard.
4. Ask one grounded clarification round if needed.
5. Initialize artifacts with `scripts/autoresearch_init_run.py`.

## Phase 2: Iterate

For each iteration:

1. Choose one hypothesis.
2. Make one focused change.
3. Run verify and guard commands.
4. Keep or discard the experiment.
5. Record the outcome with `scripts/autoresearch_record_iteration.py`.

## Phase 3: Decide

Stop when:

- the configured goal is met
- the user requests stop
- the iteration cap is reached
- the run genuinely needs human input

Background supervisors should use `scripts/autoresearch_supervisor_status.py` to make the relaunch decision from the same artifacts.
