from __future__ import annotations

import json
import subprocess
import sys

try:
    from scripts.hook_context import update_hook_context_pointer
    from scripts.hook_common import (
        build_context,
        extract_next_steps_block,
        load_last_task_complete_message,
        next_steps_has_multiple_options,
        next_steps_mentions_recommendation,
    )
except ModuleNotFoundError:
    from hook_context import update_hook_context_pointer
    from hook_common import (
        build_context,
        extract_next_steps_block,
        load_last_task_complete_message,
        next_steps_has_multiple_options,
        next_steps_mentions_recommendation,
    )


NONTERMINAL_DECISIONS = {"relaunch"}
CONTINUATION_PROMPT = (
    "Continue the current managed run.\n"
    "Do not rerun the wizard.\n"
    "If you just completed an experiment, record it before starting the next one.\n"
    "Honor keep/stop label gates, iteration limits, and duration limits before stopping.\n"
    "Do not ask the user for permission.\n"
    "Only stop when your final response no longer contains a `Next step:` or `Next steps:` section."
)
FOLLOWUP_CONTINUATION_PROMPT = (
    "Continue the current managed run.\n"
    "You are already inside a stop-hook continuation.\n"
    "Do not stop yet; record the last experiment before the next one.\n"
    "Do not ask the user for permission.\n"
    "Only stop when your final response no longer contains a `Next step:` or `Next steps:` section."
)


def run_supervisor(context) -> dict[str, object] | None:
    if context.skill_root is None:
        return None
    helper = context.skill_root / "scripts" / "autoresearch_supervisor_status.py"
    command = [
        sys.executable,
        str(helper),
        "--results-path",
        str(context.artifacts.results_path),
    ]
    if context.artifacts.state_path is not None:
        command.extend(["--state-path", str(context.artifacts.state_path)])
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=context.repo,
    )
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def emit_block(reason: str) -> None:
    payload = {
        "decision": "block",
        "reason": reason,
    }
    print(json.dumps(payload), end="")


def build_continuation_prompt(next_steps: str | None, *, followup: bool) -> str:
    lines = [FOLLOWUP_CONTINUATION_PROMPT if followup else CONTINUATION_PROMPT]
    if not isinstance(next_steps, str) or not next_steps.strip():
        return "\n".join(lines)

    if next_steps_has_multiple_options(next_steps):
        if next_steps_mentions_recommendation(next_steps):
            lines.append("Take the recommended option from the final `Next steps:` section and continue.")
        else:
            lines.append("Choose the strongest default option from the final `Next steps:` section and continue.")
    else:
        lines.append("Continue with the final `Next step:` below.")

    lines.extend(
        [
            "",
            "Final next step(s):",
            next_steps,
        ]
    )
    return "\n".join(lines)


def main() -> int:
    context = build_context(__file__)
    if context is None or context.skill_root is None:
        return 0
    if not context.session_is_managed:
        return 0
    if not context.has_active_artifacts:
        return 0

    supervisor = run_supervisor(context)
    if supervisor is None:
        return 0

    decision = supervisor.get("decision")
    if not isinstance(decision, str):
        return 0

    if decision in NONTERMINAL_DECISIONS:
        active = bool(context.payload.get("stop_hook_active"))
        last_message = load_last_task_complete_message(context.transcript_path)
        next_steps = extract_next_steps_block(last_message)
        emit_block(build_continuation_prompt(next_steps, followup=active))
    else:
        update_hook_context_pointer(
            repo=context.repo,
            active=False,
            session_mode="background" if context.opt_in_env else "foreground",
            results_path=context.artifacts.results_path,
            state_path=context.artifacts.state_path,
            launch_path=context.artifacts.launch_path,
            runtime_path=context.artifacts.runtime_path,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
