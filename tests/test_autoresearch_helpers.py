from __future__ import annotations

import json

from scripts.autoresearch_helpers import (
    RunConfig,
    WizardConfig,
    append_iteration,
    build_setup_summary,
    build_supervisor_snapshot,
    initialize_run,
    read_results_rows,
    resume_background_run,
    resolve_path,
    write_launch_manifest,
)


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
    assert payload["missing_required"] == ["mode"]
    assert any(question["id"] == "mode" for question in payload["questions"])


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
