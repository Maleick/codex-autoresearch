from __future__ import annotations

from scripts.autoresearch_hook_session_start import CHECKLIST_LINES
from scripts.autoresearch_hook_stop import CONTINUATION_PROMPT, FOLLOWUP_CONTINUATION_PROMPT
from scripts.autoresearch_hook_context import load_hook_context_pointer, write_hook_context_pointer


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


def test_session_start_hook_mentions_standing_subagent_pool():
    assert any("standing subagent pool" in line for line in CHECKLIST_LINES)
    assert any("continue by default" in line for line in CHECKLIST_LINES)


def test_stop_hook_prompts_reanchor_the_pool_before_stopping():
    assert "Re-anchor the standing subagent pool" in CONTINUATION_PROMPT
    assert "user stops the run" in CONTINUATION_PROMPT
    assert "re-anchor the standing subagent pool" in FOLLOWUP_CONTINUATION_PROMPT.lower()
