# Subagent Orchestration

Use this reference when a run should be subagent-first.

## Orchestration Model

- The main agent is the orchestrator. It owns the goal, scope, metric, direction, verify command, guard, and final keep/discard decision.
- Subagents form a standing pool for parallel context gathering, alternative synthesis, verification, and critique.
- The main agent hands bounded questions to the pool, waits for findings, and folds those findings into the next iteration before changing code again.
- Subagents surface evidence, objections, risks, and candidate next steps. They do not independently advance the run state.
- Approval belongs before launch. Once the run is launched, keep the same pool moving until the user stops the run, the configured stop condition is met, or a real `needs_human` blocker appears.

## Launch Decision

- Decide whether the standing pool should already be active during setup or only after launch.
- Default to an active pool for multi-step, uncertain, or unattended work.
- Fall back to orchestrator-only serial execution when the task is tiny or the environment cannot support clean parallel work.

## Pool Rules

- Keep the pool alive across iterations unless context drift forces a reset.
- Reuse roles where possible so context compounds instead of resetting, but only reuse heavily when the new task is highly similar to the previous context.
- Prefer a small pool with distinct jobs over one-off ad hoc spawning.
- Re-anchor the pool after every keep/discard decision with the latest goal, state, and results.
- Feed findings back into the loop before the next code change.
- Route conflicts in strict intent order: protocol, implementation, validation, then evidence.
- When repeated discards produce overlapping outputs, ask the pool for deduplicated evidence before the next change.

## Iteration Mix

- Every iteration should have a coordinator role plus explicit protocol, implementation, validation, and evidence coverage.
- In `max_parallelism` mode, prefer more concurrent branches per iteration and keep a reviewer or synthesizer active when budget allows.
- Default reviewer coverage belongs to the synthesizer or another summary/risk role when one is active.

## State Ownership

- Only the orchestrator records iterations, mutates `autoresearch-state.json`, and decides whether the latest step is `keep`, `discard`, or `needs_human`.
- Subagents may disagree, critique, or verify, but their output is supporting evidence.
- If several subagents contribute to one change, roll that evidence into one orchestrator-owned iteration result.

## Fallback Rules

- If one subagent times out, conflicts with another role, or stops adding value, replace or drop that role without stopping the whole run.
- If the whole pool becomes unhelpful, continue serially under the orchestrator instead of rerunning setup.
- Only surface `needs_human` when the orchestrator cannot continue safely after folding in the latest pool findings.
- When role or mode conflicts appear, fall back to the deterministic standing-role order instead of improvising a new ordering mid-run.

## Local Scope

- This bundle stays compact and narrower than the reference repo.
- Prefer the references in this repository over broader upstream orchestration patterns unless the user explicitly asks for them.
