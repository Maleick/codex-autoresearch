from __future__ import annotations

from argparse import Namespace
import json

import pytest

from scripts.autoresearch_helpers import (
    RunConfig,
    WizardConfig,
    append_iteration,
    build_memory_file,
    build_run_report,
    build_setup_summary,
    build_self_improvement_report,
    build_supervisor_snapshot,
    complete_background_run,
    complete_foreground_run,
    initialize_run,
    mark_background_active,
    read_results_rows,
    resume_background_run,
    resolve_path,
    set_stop_requested,
    write_launch_manifest,
)
from scripts.autoresearch_runtime_ctl import command_complete, command_launch


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
        duration="5h",
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
    assert manifest["duration"] == "5h"
    assert manifest["duration_seconds"] == 18000
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


def test_runtime_launch_dry_run_returns_preview_without_writing_files(tmp_path):
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
            iterations=50,
            duration="5h",
            required_keep_labels=["verified"],
            required_stop_labels=["ship-ready"],
            run_tag="nightly-build",
            stop_condition=None,
            baseline=None,
            fresh_start=False,
            dry_run=True,
        )
    )

    assert payload["status"] == "dry_run"
    assert payload["state_preview"]["duration_seconds"] == 18000
    assert payload["state_preview"]["label_requirements"]["keep"] == ["verified"]
    assert payload["launch_manifest_preview"]["required_stop_labels"] == ["ship-ready"]
    assert not resolve_path(repo, None, "autoresearch-state.json").exists()
    assert not resolve_path(repo, None, "autoresearch-launch.json").exists()


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


def test_wizard_includes_duration_details_for_background_runs(tmp_path):
    repo = str(tmp_path)

    payload = build_setup_summary(
        repo=repo,
        config=WizardConfig(
            goal="Make tests reliable overnight",
            mode="background",
            iterations=50,
            duration="5h",
            required_keep_labels=["verified"],
            required_stop_labels=["ship-ready"],
        ),
    )

    assert payload["duration"] == "5h"
    assert payload["duration_seconds"] == 18000
    assert payload["required_keep_labels"] == ["verified"]
    assert payload["required_stop_labels"] == ["ship-ready"]
    assert "50 iterations complete" in payload["stop_condition"]
    assert "5h elapses" in payload["stop_condition"]
    assert "ship-ready" in payload["stop_condition"]


def test_wizard_loads_existing_memory_into_setup_summary(tmp_path):
    repo = str(tmp_path)
    resolve_path(repo, None, "autoresearch-memory.md").write_text(
        "# Autoresearch Memory\n\n- Keep the narrowed scope.\n- Change the verify command only if it flakes.\n",
        encoding="utf-8",
    )

    payload = build_setup_summary(
        repo=repo,
        config=WizardConfig(
            goal="Continue prior run",
            mode="foreground",
        ),
    )

    assert payload["memory"]["loaded"] is True
    assert payload["memory"]["path"].endswith("autoresearch-memory.md")
    assert "Keep the narrowed scope." in payload["memory"]["excerpt"]


def test_wizard_prompts_for_duration_on_background_runs(tmp_path):
    repo = str(tmp_path)

    payload = build_setup_summary(
        repo=repo,
        config=WizardConfig(
            goal="Make tests reliable overnight",
            mode="background",
        ),
    )

    assert any(question["id"] == "duration" for question in payload["questions"])


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


def test_append_iteration_rejects_keep_without_required_keep_labels(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Reduce flaky tests",
        metric="failing tests",
        direction="lower",
        verify="pytest tests/integration",
        mode="foreground",
        required_keep_labels=["verified"],
    )
    initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )

    with pytest.raises(RuntimeError):
        append_iteration(
            repo=repo,
            results_path_value=None,
            state_path_value=None,
            decision="keep",
            metric_value="6",
            verify_status="pass",
            guard_status="skip",
            hypothesis="seed",
            change_summary="missing keep label",
            labels=["reviewed"],
            note=None,
            iteration=None,
        )


def test_append_iteration_marks_stop_ready_when_stop_labels_satisfied(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Reduce flaky tests",
        metric="failing tests",
        direction="lower",
        verify="pytest tests/integration",
        mode="foreground",
        required_keep_labels=["verified"],
        required_stop_labels=["ship-ready"],
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
        metric_value="6",
        verify_status="pass",
        guard_status="skip",
        hypothesis="seed",
        change_summary="meets label gates",
        labels=["verified", "ship-ready"],
        note=None,
        iteration=None,
    )

    assert state["flags"]["stop_ready"] is True
    assert state["last_iteration"]["stop_labels_satisfied"] is True


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


def test_initialize_run_persists_duration_and_deadline(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Lower build time",
        metric="build seconds",
        direction="lower",
        verify="pytest",
        mode="background",
        duration="5h",
    )

    state = initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )

    assert state["duration"] == "5h"
    assert state["duration_seconds"] == 18000
    assert state["deadline_at"] is not None


def test_initialize_run_persists_loaded_memory_baseline(tmp_path):
    repo = str(tmp_path)
    resolve_path(repo, None, "autoresearch-memory.md").write_text(
        "# Autoresearch Memory\n\n- Keep the verify command stable.\n",
        encoding="utf-8",
    )
    config = RunConfig(
        goal="Lower build time",
        metric="build seconds",
        direction="lower",
        verify="pytest",
        mode="foreground",
    )

    state = initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )

    assert state["memory"]["loaded"] is True
    assert state["memory"]["path"].endswith("autoresearch-memory.md")
    assert "Keep the verify command stable." in state["memory"]["excerpt"]


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


def test_complete_foreground_run_marks_state_complete(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Lower build time",
        metric="build seconds",
        direction="lower",
        verify="pytest",
        mode="foreground",
    )
    initialize_run(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
        config=config,
        fresh_start=False,
    )
    state = complete_foreground_run(repo=repo, state_path_value=None)

    assert state["status"] == "completed"
    assert state["flags"]["background_active"] is False
    assert state["flags"]["stop_requested"] is False


def test_build_run_report_includes_label_gates(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Reduce flaky tests",
        metric="failing tests",
        direction="lower",
        verify="pytest tests/integration",
        mode="foreground",
        required_keep_labels=["verified"],
        required_stop_labels=["ship-ready"],
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
        metric_value="6",
        verify_status="pass",
        guard_status="skip",
        hypothesis="seed",
        change_summary="meets label gates",
        labels=["verified", "ship-ready"],
        note=None,
        iteration=None,
    )

    report = build_run_report(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
    )

    assert "Required keep labels" in report
    assert "ship-ready" in report
    assert "Stop ready" in report


def test_runtime_launch_manifest_includes_loaded_memory_baseline(tmp_path):
    repo = str(tmp_path)
    resolve_path(repo, None, "autoresearch-memory.md").write_text(
        "# Autoresearch Memory\n\n- Keep the narrowed scope.\n",
        encoding="utf-8",
    )
    config = RunConfig(
        goal="Lower build time",
        metric="build seconds",
        direction="lower",
        verify="npm run build",
        mode="background",
        duration="5h",
        run_tag="nightly-build",
    )

    manifest = write_launch_manifest(
        repo=repo,
        launch_path_value=None,
        config=config,
        results_path_value=None,
        state_path_value=None,
    )

    assert manifest["memory"]["loaded"] is True
    assert manifest["memory"]["path"].endswith("autoresearch-memory.md")
    assert "Keep the narrowed scope." in manifest["memory"]["excerpt"]


def test_build_self_improvement_report_includes_learnings_and_defaults(tmp_path):
    repo = str(tmp_path)
    resolve_path(repo, None, "autoresearch-memory.md").write_text(
        "# Autoresearch Memory\n\n- Keep the narrowed scope.\n",
        encoding="utf-8",
    )
    config = RunConfig(
        goal="Reduce flaky tests",
        metric="failing tests",
        direction="lower",
        verify="pytest tests/integration",
        mode="foreground",
        guard="python scripts/autoresearch_supervisor_status.py",
        iterations=50,
        duration="5h",
        required_keep_labels=["verified"],
        required_stop_labels=["ship-ready"],
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
        metric_value="6",
        verify_status="pass",
        guard_status="pass",
        hypothesis="seed",
        change_summary="meets all gates",
        labels=["verified", "ship-ready"],
        note=None,
        iteration=None,
    )

    report = build_self_improvement_report(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
    )

    assert "# Autoresearch Self-Improvement" in report
    assert "Keep the current direction of change" in report
    assert "Carry forward the required stop labels: ship-ready." in report
    assert "Iterations cap: 50" in report
    assert "Duration budget: 5h" in report
    assert "Memory baseline:" in report
    assert "Load `autoresearch-memory.md` before the next run" in report


def test_build_memory_file_captures_stop_gate_follow_up(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Reduce flaky tests",
        metric="failing tests",
        direction="lower",
        verify="pytest tests/integration",
        mode="foreground",
        required_keep_labels=["verified"],
        required_stop_labels=["ship-ready"],
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
        metric_value="6",
        verify_status="pass",
        guard_status="skip",
        hypothesis="seed",
        change_summary="kept but not stop-ready",
        labels=["verified"],
        note=None,
        iteration=None,
    )

    memory = build_memory_file(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
    )

    assert "# Autoresearch Memory" in memory
    assert "Do not treat the run as stop-ready until these stop labels are recorded: ship-ready." in memory
    assert "Required keep labels: verified" in memory
    assert "Required stop labels: ship-ready" in memory


def test_command_complete_writes_self_improvement_and_memory_artifacts(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Reduce flaky tests overnight",
        metric="failing tests",
        direction="lower",
        verify="pytest tests/integration",
        mode="background",
        required_keep_labels=["verified"],
        required_stop_labels=["ship-ready"],
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
        metric_value="6",
        verify_status="pass",
        guard_status="pass",
        hypothesis="seed",
        change_summary="ready to complete",
        labels=["verified", "ship-ready"],
        note=None,
        iteration=None,
    )

    payload = command_complete(
        Namespace(
            repo=repo,
            state_path=None,
            results_path=None,
            report_path=None,
            self_improvement_path=None,
            memory_path=None,
        )
    )

    self_improvement_path = resolve_path(repo, None, "autoresearch-self-improvement.md")
    memory_path = resolve_path(repo, None, "autoresearch-memory.md")

    assert payload["status"] == "completed"
    assert payload["self_improvement_path"] == str(self_improvement_path)
    assert payload["memory_path"] == str(memory_path)
    assert self_improvement_path.exists()
    assert memory_path.exists()
    assert "# Autoresearch Self-Improvement" in self_improvement_path.read_text(encoding="utf-8")
    assert "# Autoresearch Memory" in memory_path.read_text(encoding="utf-8")


def test_supervisor_status_stops_when_duration_elapsed(tmp_path):
    repo = str(tmp_path)
    config = RunConfig(
        goal="Lower build time",
        metric="build seconds",
        direction="lower",
        verify="pytest",
        mode="background",
        duration="5h",
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
    payload["deadline_at"] = "2000-01-01T00:00:00Z"
    state_path.write_text(json.dumps(payload), encoding="utf-8")

    snapshot = build_supervisor_snapshot(
        repo=repo,
        results_path_value=None,
        state_path_value=None,
    )

    assert snapshot["decision"] == "stop"
    assert snapshot["reason"] == "duration_elapsed"


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

