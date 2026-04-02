from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

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


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

autoresearch_hook_session_start = importlib.import_module("autoresearch_hook_session_start")
autoresearch_hook_stop = importlib.import_module("autoresearch_hook_stop")


def _make_hook_context() -> SimpleNamespace:
    artifacts = SimpleNamespace(
        results_path=REPO_ROOT / "research-results.tsv",
        state_path=REPO_ROOT / "autoresearch-state.json",
        launch_path=None,
        runtime_path=None,
    )
    return SimpleNamespace(
        skill_root=REPO_ROOT,
        session_is_autoresearch=True,
        has_active_artifacts=True,
        payload={},
        repo=REPO_ROOT,
        opt_in_env=False,
        artifacts=artifacts,
    )


def test_session_start_hook_mentions_standing_subagent_pool(monkeypatch, capsys):
    monkeypatch.setattr(
        autoresearch_hook_session_start,
        "build_context",
        lambda _path: _make_hook_context(),
    )

    assert autoresearch_hook_session_start.main() == 0
    output = capsys.readouterr().out

    assert "standing subagent pool" in output
    assert "continue by default unless the user stops the run" in output


def test_stop_hook_blocks_relaunch_with_continuation_prompt(monkeypatch, capsys):
    monkeypatch.setattr(
        autoresearch_hook_stop,
        "build_context",
        lambda _path: _make_hook_context(),
    )
    monkeypatch.setattr(
        autoresearch_hook_stop,
        "run_supervisor",
        lambda _context: {"decision": "relaunch"},
    )

    assert autoresearch_hook_stop.main() == 0
    output = capsys.readouterr().out

    assert '"decision": "block"' in output
    assert "The run was already approved" in output
    assert "standing subagent pool" in output


def test_stop_hook_allows_terminal_decision_and_clears_pointer(monkeypatch, capsys):
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        autoresearch_hook_stop,
        "build_context",
        lambda _path: _make_hook_context(),
    )
    monkeypatch.setattr(
        autoresearch_hook_stop,
        "run_supervisor",
        lambda _context: {"decision": "needs_human"},
    )
    monkeypatch.setattr(
        autoresearch_hook_stop,
        "update_hook_context_pointer",
        lambda **kwargs: calls.append(kwargs),
    )

    assert autoresearch_hook_stop.main() == 0
    assert capsys.readouterr().out == ""
    assert calls and calls[0]["active"] is False
