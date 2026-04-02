# Subagent Orchestration

Use this reference when a run should be subagent-first.

## Orchestration Model

- The main agent is the orchestrator. It owns the goal, scope, metric, direction, verify command, guard, and final keep/discard decision.
- Subagents form a standing pool for parallel context gathering, alternative synthesis, verification, and critique.
- The main agent hands bounded questions to the pool, waits for findings, and folds those findings into the next iteration before changing code again.
- Subagents surface evidence, objections, risks, and candidate next steps. They do not independently advance the run state.
- Use `python3 scripts/autoresearch_subagent_plan.py` when you want a stable starting pool instead of improvising roles each round.

## Launch Decision

- Decide whether the standing pool should be active during the setup phase, before the user says "go".
- Default to a standing pool for multi-step or high-uncertainty work.
- Fall back to serial orchestrator-only execution when the repo is tiny, the task is trivial, or the environment cannot support parallel context gathering cleanly.

## Pool Rules

- Keep the pool alive across iterations unless context drift forces a reset.
- Reuse roles where possible so context compounds instead of resetting.
- Prefer a small pool with distinct jobs over one-off ad hoc spawning.
- Re-anchor the pool after every keep/discard decision with the latest goal, state, and results.
- Feed findings back into the loop before the next code change.
- Keep the pool bounded. The orchestrator plus up to five focused subagents is the default ceiling for this bundle.

## State Ownership

- Only the orchestrator records iterations, mutates `autoresearch-state.json`, and decides whether the latest step is `keep`, `discard`, or `needs_human`.
- Subagents may disagree, critique, or verify, but their output is supporting evidence.
- If several subagents contribute to one change, roll that evidence into one orchestrator-owned iteration result.

## Fallback Rules

- If a subagent times out, conflicts with another role, or stops adding value, replace or drop that role without stopping the whole run.
- If the whole pool becomes unhelpful, continue serially under the orchestrator instead of re-running setup.
- Only surface `needs_human` when the orchestrator cannot continue safely after folding in the latest pool findings.

## Local Scope

- This bundle stays compact and narrower than the reference repo.
- Prefer the references in this repository over broader upstream orchestration patterns unless the user explicitly asks for them.
