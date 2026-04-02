from __future__ import annotations

from argparse import Namespace
import json

import pytest

from scripts.autoresearch_helpers import (
    RunConfig,
    WizardConfig,
    append_iteration,
    build_setup_summary,
    build_supervisor_snapshot,
    complete_background_run,
    initialize_run,
    mark_background_active,
    read_results_rows,
    resume_background_run,
    resolve_path,
    set_stop_requested,
    write_launch_manifest,
)
from scripts.autoresearch_runtime_ctl import command_launch


def test_initialize_run_creates_state_and_results(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Reduce lint failures",
        metric="lint errors",
        direction="lower",
        verify="npm run lint",
        mode="foreground",
        guard="npm test",
        iterations=5,
        baseline="12",
    )

    state = initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )

    results_path = resolve_path(repo, None, "research-results.tsv")
    state_path = resolve_path(repo, None, "autoresearch-state.json")

    assert results_path.exists()
    assert state_path.exists()
    assert state["goal"] == "Reduce lint failures"
    assert state["metric"]["baseline"] == "12"
    assert state["stats"]["total_iterations"] == 0


def test_record_iteration_updates_state_and_results(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Reduce flaky tests",
        metric="failing tests",
        direction="lower",
        verify="pytest tests/integration",
        mode="foreground",
        baseline="9",
    )
    initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )

    state = append_iteration(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        decision="keep",
        metric_value="7",
        verify_status="pass",
        guard_status="skip",
        hypothesis="stabilize network retry logic",
        change_summary="cap retries and widen timeout budget",
        labels=["network", "retry"],
        note=None,
        iteration=None,
    )

    rows = read_results_rows(resolve_path(repo, None, "research-results.tsv"))
    assert len(rows) == 1
    assert rows[0]["decision"] == "keep"
    assert rows[0]["metric_value"] == "7"
    assert state["metric"]["best"] == "7"
    assert state["stats"]["kept"] == 1
    assert state["stats"]["consecutive_discards"] == 0


def test_supervisor_status_stops_when_requested(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Improve type safety",
        metric="unsafe casts",
        direction="lower",
        verify="npm run typecheck",
        mode="background",
        iterations=3,
        baseline="20",
    )
    initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )
    state_path = resolve_path(repo, None, "autoresearch-state.json")
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["flags"]["stop_requested"] = True
    state_path.write_text(json.dumps(payload), encoding="utf-8")

    snapshot = build_supervisor_snapshot(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
    )

    assert snapshot["decision"] == "stop"
    assert snapshot["reason"] == "stop_requested"


def test_set_stop_requested_rejects_foreground_run(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Improve type safety",
        metric="unsafe casts",
        direction="lower",
        verify="npm run typecheck",
        mode="foreground",
    )
    initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )

    with pytest.raises(RuntimeError):
        set_stop_requested(repo=repo, state_path_value=None)


def test_mark_background_active_rejects_foreground_run(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Improve type safety",
        metric="unsafe casts",
        direction="lower",
        verify="npm run typecheck",
        mode="foreground",
    )
    initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )

    with pytest.raises(RuntimeError):
        mark_background_active(repo=repo, state_path_value=None, active=True)


def test_runtime_launch_manifest_points_at_artifacts(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Lower build time",
        metric="build seconds",
        direction="lower",
        verify="npm run build",
        mode="background",
        run_tag="nightly-build",
    )

    manifest = write_launch_manifest(
        repo=repo,
        launch_path_value=None,
        config=config,
        results_path_value=None,
        state_path_value=None,
    )

    assert manifest["mode"] == "background"
    assert manifest["run_tag"] == "nightly-build"
    assert manifest["artifact_paths"]["launch"].endswith("autoresearch-launch.json")


def test_runtime_launch_returns_running_state(tmp_path):
    repo = str(tmp_path)

    payload = command_launch(
        Namespace(
            repo=repo,
            results_path=None,
            state_path=None,
            launch_path=None,
            scope=None,
            goal="Lower build time",
            metric="build seconds",
            direction="lower",
            verify="npm run build",
            guard=None,
            iterations=None,
            run_tag="nightly-build",
            stop_condition=None,
            baseline=None,
            fresh_start=False,
        )
    )

    assert payload["status"] == "launched"
    assert payload["state"]["status"] == "running"
    assert payload["state"]["flags"]["background_active"] is True


def test_write_launch_manifest_requires_fresh_start_to_replace_existing(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Lower build time",
        metric="build seconds",
        direction="lower",
        verify="npm run build",
        mode="background",
    )

    write_launch_manifest(
        repo=repo,
        launch_path_value=None,
        config=config,
        results_path_value=None,
        state_path_value=None,
    )
    launch_path = resolve_path(repo, None, "autoresearch-launch.json")
    original_contents = launch_path.read_text(encoding="utf-8")

    with pytest.raises(RuntimeError):
        write_launch_manifest(
            repo=repo,
            launch_path_value=None,
            config=config,
            results_path_value=None,
            state_path_value=None,
        )

    manifest = write_launch_manifest(
        repo=repo,
        launch_path_value=None,
        config=config,
        results_path_value=None,
        state_path_value=None,
        fresh_start=True,
    )
    archive_path = launch_path.with_name("autoresearch-launch.prev.json")

    assert archive_path.exists()
    assert archive_path.read_text(encoding="utf-8") == original_contents
    assert manifest["artifact_paths"]["launch"].endswith("autoresearch-launch.json")


def test_wizard_infers_verify_guard_and_missing_fields(tmp_path):
    repo = str(tmp_path)
    (tmp_path / "tests").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "autoresearch_supervisor_status.py").write_text("", encoding="utf-8")

    payload = build_setup_summary(
        repo=repo,
        config=WizardConfig(goal="Make tests reliable"),
    )

    assert payload["verify"] == "pytest"
    assert payload["guard"] == "python scripts/autoresearch_supervisor_status.py"
    assert payload["direction"] == "lower"
    assert payload["missing_required"] == ["mode", "scope"]
    assert payload["scope"] == tmp_path.name
    assert any(question["id"] == "mode" for question in payload["questions"])
    assert any(question["id"] == "scope" for question in payload["questions"])


def test_wizard_rejects_invalid_direction(tmp_path):
    repo = str(tmp_path)
    with pytest.raises(RuntimeError):
        build_setup_summary(
            repo=repo,
            config=WizardConfig(
                goal="Reduce flake",
                mode="foreground",
                direction="sideways",
            ),
        )


def test_initialize_run_rejects_invalid_iteration_cap(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Stabilize startup",
        metric="startup_time",
        direction="lower",
        verify="pytest",
        mode="foreground",
        iterations=0,
    )

    with pytest.raises(RuntimeError):
        initialize_run(
            repo=repo,
            results_path_value=None,
            state_path_value=None,
            config=config,
            fresh_start=False,
        )


def test_append_iteration_rejects_reused_iteration_number(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Reduce flaky tests",
        metric="failing tests",
        direction="lower",
        verify="pytest tests/integration",
        mode="foreground",
    )
    initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )
    append_iteration(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        decision="keep",
        metric_value="8",
        verify_status="pass",
        guard_status="skip",
        hypothesis="seed",
        change_summary="initial seed",
        labels=["seed"],
        note=None,
        iteration=None,
    )

    with pytest.raises(RuntimeError):
        append_iteration(
            repo=repo,
            results_path_value=None,
            state_path_value=None,
            decision="keep",
            metric_value="7",
            verify_status="pass",
            guard_status="skip",
            hypothesis="seed",
            change_summary="reused number",
            labels=["seed"],
            note=None,
            iteration=1,
        )


def test_needs_human_iteration_resets_discard_streak(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Reduce flaky tests",
        metric="failing tests",
        direction="lower",
        verify="pytest tests/integration",
        mode="foreground",
    )
    initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )
    append_iteration(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        decision="discard",
        metric_value="8",
        verify_status="pass",
        guard_status="skip",
        hypothesis="seed",
        change_summary="discarded",
        labels=["seed"],
        note=None,
        iteration=None,
    )
    state = append_iteration(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        decision="needs_human",
        metric_value="6",
        verify_status="pass",
        guard_status="skip",
        hypothesis="seed",
        change_summary="needs manual review",
        labels=["review"],
        note=None,
        iteration=None,
    )

    assert state["stats"]["consecutive_discards"] == 0
    assert state["flags"]["needs_human"] is True


def test_resume_background_run_clears_stop_requested(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Lower build time",
        metric="build seconds",
        direction="lower",
        verify="pytest",
        mode="background",
    )
    initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )
    state_path = resolve_path(repo, None, "autoresearch-state.json")
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["flags"]["stop_requested"] = True
    payload["flags"]["background_active"] = False
    payload["status"] = "stopping"
    state_path.write_text(json.dumps(payload), encoding="utf-8")

    resumed = resume_background_run(repo=repo, state_path_value=None)

    assert resumed["flags"]["stop_requested"] is False
    assert resumed["flags"]["background_active"] is True
    assert resumed["status"] == "running"


def test_resume_background_run_clears_needs_human_and_relaunches(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Lower build time",
        metric="build seconds",
        direction="lower",
        verify="pytest",
        mode="background",
    )
    initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )
    state_path = resolve_path(repo, None, "autoresearch-state.json")
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["flags"]["needs_human"] = True
    payload["flags"]["background_active"] = False
    payload["status"] = "stopped"
    state_path.write_text(json.dumps(payload), encoding="utf-8")

    resumed = resume_background_run(repo=repo, state_path_value=None)
    snapshot = build_supervisor_snapshot(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
    )

    assert resumed["flags"]["needs_human"] is False
    assert resumed["flags"]["background_active"] is True
    assert resumed["status"] == "running"
    assert snapshot["decision"] == "relaunch"


def test_resume_background_run_disallows_completed_runs(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Lower build time",
        metric="build seconds",
        direction="lower",
        verify="pytest",
        mode="background",
    )
    initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )
    state_path = resolve_path(repo, None, "autoresearch-state.json")
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["status"] = "completed"
    state_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError):
        resume_background_run(repo=repo, state_path_value=None)


def test_complete_background_run_marks_state_complete(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Lower build time",
        metric="build seconds",
        direction="lower",
        verify="pytest",
        mode="background",
    )
    initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )
    state = complete_background_run(repo=repo, state_path_value=None)

    assert state["status"] == "completed"
    assert state["flags"]["background_active"] is False
    assert state["flags"]["stop_requested"] is False


@pytest.mark.parametrize(
    ("field_name", "value"),
    [("verify_status", "unknown"), ("guard_status", "later")],
)
def test_append_iteration_rejects_invalid_result_statuses(tmp_path, field_name, value):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Reduce flaky tests",
        metric="failing tests",
        direction="lower",
        verify="pytest tests/integration",
        mode="foreground",
    )
    initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )

    kwargs = {
        "repo": repo,
        "results_path_value": None,
        "state_path_value": None,
        "decision": "keep",
        "metric_value": "7",
        "verify_status": "pass",
        "guard_status": "skip",
        "hypothesis": "stabilize network retry logic",
        "change_summary": "cap retries and widen timeout budget",
        "labels": ["network", "retry"],
        "note": None,
        "iteration": None,
    }
    kwargs[field_name] = value

    with pytest.raises(RuntimeError):
        append_iteration(**kwargs)

