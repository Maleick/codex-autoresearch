from __future__ import annotations

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
