from __future__ import annotations

import json
from types import SimpleNamespace

from scripts.hook_common import (
    extract_next_steps_block,
    load_last_task_complete_message,
    next_steps_has_multiple_options,
    next_steps_mentions_recommendation,
)
from scripts.hook_context import load_hook_context_pointer, write_hook_context_pointer
from scripts.hook_start import CHECKLIST_LINES
from scripts import hook_stop
from scripts.hook_stop import (
    CONTINUATION_PROMPT,
    FOLLOWUP_CONTINUATION_PROMPT,
    build_continuation_prompt,
)


def test_hook_context_round_trips_repo_relative_paths(tmp_path):
    repo = tmp_path
    results_path = repo / "research-results.tsv"
    state_path = repo / "autoresearch-state.json"
    launch_path = repo / "autoresearch-launch.json"
    results_path.write_text("", encoding="utf-8")
    state_path.write_text("{}", encoding="utf-8")
    launch_path.write_text("{}", encoding="utf-8")

    write_hook_context_pointer(
        repo=repo,
        active=True,
        session_mode="background",
        results_path=results_path,
        state_path=state_path,
        launch_path=launch_path,
        runtime_path=None,
    )

    pointer = load_hook_context_pointer(repo)

    assert pointer is not None
    assert pointer.active is True
    assert pointer.session_mode == "background"
    assert pointer.results_path == results_path.resolve()
    assert pointer.state_path == state_path.resolve()
    assert pointer.launch_path == launch_path.resolve()


def test_session_start_hook_mentions_managed_run_defaults():
    assert any("fresh managed run" in line for line in CHECKLIST_LINES)
    assert any("continue by default" in line for line in CHECKLIST_LINES)


def test_stop_hook_default_prompts_require_next_step_exhaustion():
    assert "Do not ask the user for permission." in CONTINUATION_PROMPT
    assert "Next step:" in CONTINUATION_PROMPT
    assert "already inside a stop-hook continuation" in FOLLOWUP_CONTINUATION_PROMPT


def test_load_last_task_complete_message_prefers_latest_completion(tmp_path):
    transcript_path = tmp_path / "session.jsonl"
    transcript_path.write_text(
        "\n".join(
            [
                json.dumps({"type": "event_msg", "payload": {"type": "task_complete", "last_agent_message": "first"}}),
                json.dumps({"type": "event_msg", "payload": {"type": "task_complete", "last_agent_message": "second"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert load_last_task_complete_message(transcript_path) == "second"


def test_extract_next_steps_supports_inline_and_block_forms():
    inline = "Summary\n\nNext step: Tighten branch protection on master."
    block = "Summary\n\nNext steps:\n1. Tighten branch protection (Recommended)\n2. Document the gate\n\n**Verification**"

    assert extract_next_steps_block(inline) == "Tighten branch protection on master."
    assert extract_next_steps_block(block) == "1. Tighten branch protection (Recommended)\n2. Document the gate"


def test_next_steps_detection_distinguishes_multiple_options_and_recommendations():
    next_steps = "1. Tighten branch protection (Recommended)\n2. Document the gate"

    assert next_steps_has_multiple_options(next_steps) is True
    assert next_steps_mentions_recommendation(next_steps) is True


def test_build_continuation_prompt_uses_recommended_or_default_language():
    recommended_prompt = build_continuation_prompt(
        "1. Tighten branch protection (Recommended)\n2. Document the gate",
        followup=False,
    )
    default_prompt = build_continuation_prompt(
        "1. Tighten branch protection\n2. Document the gate",
        followup=True,
    )

    assert "recommended option" in recommended_prompt
    assert "Choose the strongest default option" in default_prompt
    assert "Final next step(s):" in recommended_prompt


def test_stop_hook_state_decision_wins_over_next_steps(monkeypatch, tmp_path):
    context = SimpleNamespace(
        skill_root=tmp_path,
        session_is_managed=True,
        has_active_artifacts=True,
        payload={"stop_hook_active": False},
        transcript_path=tmp_path / "session.jsonl",
        repo=tmp_path,
        opt_in_env=False,
        artifacts=SimpleNamespace(
            results_path=tmp_path / "research-results.tsv",
            state_path=tmp_path / "autoresearch-state.json",
            launch_path=None,
            runtime_path=None,
        ),
    )

    emitted: list[str] = []
    updates: list[dict[str, object]] = []
    monkeypatch.setattr(hook_stop, "build_context", lambda _: context)
    monkeypatch.setattr(hook_stop, "run_supervisor", lambda _: {"decision": "stop"})
    monkeypatch.setattr(hook_stop, "emit_block", emitted.append)
    monkeypatch.setattr(hook_stop, "update_hook_context_pointer", lambda **kwargs: updates.append(kwargs))

    assert hook_stop.main() == 0
    assert emitted == []
    assert updates and updates[0]["active"] is False
