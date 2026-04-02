from __future__ import annotations

import sys
from types import SimpleNamespace

from scripts.run_contributor_gate import (
    build_contributor_gate_plan,
    main,
    run_contributor_gate_plan,
    run_runtime_smoke,
)


def test_packaging_gate_plan_covers_distribution_surface(tmp_path):
    plan = build_contributor_gate_plan(tmp_path, "packaging", python_executable="/opt/python")

    assert [step.label for step in plan] == [
        "sync packaged plugin payload",
        "validate plugin distribution metadata",
        "run plugin distribution tests",
    ]
    assert plan[0].argv == (
        "/opt/python",
        str(tmp_path / "scripts" / "sync_plugin_payload.py"),
        "--check",
    )
    assert plan[1].argv == (
        "/opt/python",
        str(tmp_path / "scripts" / "check_plugin_distribution.py"),
    )
    assert plan[2].argv == (
        "/opt/python",
        "-m",
        "pytest",
        "tests/test_plugin_distribution.py",
        "-q",
    )


def test_skill_gate_plan_adds_full_pytest_suite(tmp_path):
    plan = build_contributor_gate_plan(tmp_path, "skill", python_executable="/opt/python")

    assert [step.label for step in plan] == [
        "sync packaged plugin payload",
        "validate plugin distribution metadata",
        "run full pytest suite",
    ]
    assert plan[-1].argv == ("/opt/python", "-m", "pytest", "-q")


def test_run_contributor_gate_plan_stops_after_failure(tmp_path, capsys):
    plan = build_contributor_gate_plan(tmp_path, "packaging")
    return_codes = iter([0, 2, 0])
    calls: list[tuple[tuple[str, ...], object]] = []

    def runner(argv, cwd=None):
        calls.append((tuple(argv), cwd))
        return SimpleNamespace(returncode=next(return_codes))

    exit_code = run_contributor_gate_plan(plan, repo_root=tmp_path, runner=runner)

    assert exit_code == 2
    assert len(calls) == 2
    assert calls[0][1] == tmp_path
    output = capsys.readouterr().out
    assert "Contributor gate failed at validate plugin distribution metadata with exit code 2" in output


def test_runtime_smoke_exercises_background_control_surface(tmp_path):
    calls: list[tuple[str, tuple[str, ...], object]] = []

    def fake_runner(step):
        calls.append((step.label, step.argv, step.cwd))
        return SimpleNamespace(returncode=0)

    run_runtime_smoke(tmp_path, python_executable="/opt/python", runner=fake_runner)

    assert [label for label, _, _ in calls] == [
        "runtime smoke: launch",
        "runtime smoke: status",
        "runtime smoke: stop",
        "runtime smoke: resume",
        "runtime smoke: complete",
    ]
    runtime_ctl = str(tmp_path / "scripts" / "autoresearch_runtime_ctl.py")
    for _, argv, cwd in calls:
        assert argv[0] == "/opt/python"
        assert argv[1] == runtime_ctl
        assert cwd == tmp_path

    assert calls[0][1][2] == "launch"
    assert "--duration" in calls[0][1]
    assert calls[-1][1][2] == "complete"


def test_main_dry_run_prints_plan(tmp_path, capsys):
    exit_code = main(
        [
            "skill",
            "--repo",
            str(tmp_path),
            "--python",
            "/opt/python",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "1. sync packaged plugin payload:" in output
    assert "/opt/python -m pytest -q" in output
    assert "runtime-smoke: temp repo launch/status/stop/resume/complete" in output
