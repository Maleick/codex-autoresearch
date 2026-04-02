from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import uuid4


RESULTS_HEADER = [
    "timestamp",
    "iteration",
    "decision",
    "metric_value",
    "verify_status",
    "guard_status",
    "hypothesis",
    "change_summary",
    "labels",
    "note",
]

DEFAULT_RESULTS_PATH = "research-results.tsv"
DEFAULT_STATE_PATH = "autoresearch-state.json"
DEFAULT_LAUNCH_PATH = "autoresearch-launch.json"


class AutoresearchError(RuntimeError):
    pass


@dataclass
class RunConfig:
    goal: str
    metric: str
    direction: str
    verify: str
    mode: str
    guard: str | None = None
    iterations: int | None = None
    run_tag: str | None = None
    stop_condition: str | None = None
    baseline: str | None = None


@dataclass
class WizardConfig:
    goal: str | None = None
    scope: str | None = None
    metric: str | None = None
    direction: str | None = None
    verify: str | None = None
    guard: str | None = None
    mode: str | None = None
    iterations: int | None = None
    stop_condition: str | None = None
    rollback_strategy: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_repo(repo: str | None) -> Path:
    if repo:
        return Path(repo).expanduser().resolve()
    return Path.cwd().resolve()


def resolve_path(repo: str | None, value: str | None, default_name: str) -> Path:
    if value:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = resolve_repo(repo) / path
        return path.resolve()
    return (resolve_repo(repo) / default_name).resolve()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, content: str) -> None:
    ensure_parent(path)
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def archive_existing(path: Path) -> Path | None:
    if not path.exists():
        return None

    if path.suffix:
        archive_path = path.with_name(f"{path.stem}.prev{path.suffix}")
    else:
        archive_path = path.with_name(f"{path.name}.prev")
    path.replace(archive_path)
    return archive_path


def parse_metric(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise AutoresearchError(f"Invalid metric value: {value}") from exc


def decimal_to_json(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.normalize(), "f")


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AutoresearchError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_results_header(path: Path) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(RESULTS_HEADER)


def read_results_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [dict(row) for row in reader]


def append_results_row(path: Path, row: dict[str, Any]) -> None:
    if not path.exists():
        write_results_header(path)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=RESULTS_HEADER, lineterminator="\n")
        normalized = {field: row.get(field, "") for field in RESULTS_HEADER}
        writer.writerow(normalized)


def infer_verify_command(repo: str | None) -> str:
    root = resolve_repo(repo)
    if (root / "pytest.ini").exists() or (root / "tests").exists():
        return "pytest"
    if (root / "package.json").exists():
        return "npm test"
    return "<set verify command>"


def infer_guard_command(repo: str | None, verify: str | None) -> str | None:
    root = resolve_repo(repo)
    if (root / "scripts" / "autoresearch_supervisor_status.py").exists() and verify != "python scripts/autoresearch_supervisor_status.py":
        return "python scripts/autoresearch_supervisor_status.py"
    return None


def normalize_mode(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized not in {"foreground", "background"}:
        raise AutoresearchError(f"Unsupported mode: {value}")
    return normalized


def build_setup_summary(*, repo: str | None, config: WizardConfig) -> dict[str, Any]:
    verify = config.verify or infer_verify_command(repo)
    guard = config.guard if config.guard is not None else infer_guard_command(repo, verify)
    direction = config.direction or "lower"
    mode = normalize_mode(config.mode)
    stop_condition = config.stop_condition or (
        f"stop when `{verify}` reaches the target metric"
        if verify and verify != "<set verify command>"
        else "stop when the target metric is met"
    )
    rollback_strategy = config.rollback_strategy or "discard the current experiment and keep the last verified state"
    metric = config.metric or "primary verify metric"
    scope = config.scope or "current repository"

    missing_required: list[str] = []
    if not config.goal:
        missing_required.append("goal")
    if not config.mode:
        missing_required.append("mode")
    if verify == "<set verify command>":
        missing_required.append("verify")

    questions: list[dict[str, str]] = []
    if not config.goal:
        questions.append(
            {
                "id": "goal",
                "prompt": "What outcome should this run optimize for?",
                "reason": "The loop needs one concrete result to chase.",
            }
        )
    if not config.metric:
        questions.append(
            {
                "id": "metric",
                "prompt": f"What metric should track progress? Default: `{metric}`",
                "reason": "The loop keeps or discards experiments based on a measurable result.",
            }
        )
    if verify == "<set verify command>":
        questions.append(
            {
                "id": "verify",
                "prompt": "What command should mechanically verify the metric?",
                "reason": "The loop should not keep changes on intuition alone.",
            }
        )
    if config.guard is None and guard:
        questions.append(
            {
                "id": "guard",
                "prompt": f"Should this run keep `{guard}` as a guard command, replace it, or use none?",
                "reason": "A guard catches regressions that the primary metric can miss.",
            }
        )
    elif config.guard == "":
        guard = None
    if not config.mode:
        questions.append(
            {
                "id": "mode",
                "prompt": "Should the run stay in `foreground` or move to `background`?",
                "reason": "The skill requires an explicit run-mode choice before launch.",
            }
        )

    return {
        "goal": config.goal,
        "scope": scope,
        "metric": metric,
        "direction": direction,
        "verify": verify,
        "guard": guard,
        "mode": mode,
        "iterations_cap": config.iterations,
        "stop_condition": stop_condition,
        "rollback_strategy": rollback_strategy,
        "missing_required": missing_required,
        "questions": questions,
    }


def metric_is_better(candidate: Decimal, current: Decimal | None, direction: str) -> bool:
    if current is None:
        return True
    if direction == "lower":
        return candidate < current
    if direction == "higher":
        return candidate > current
    raise AutoresearchError(f"Unsupported direction: {direction}")


def make_state_payload(config: RunConfig, results_path: Path, state_path: Path) -> dict[str, Any]:
    baseline_metric = parse_metric(config.baseline)
    now = utc_now()
    run_id = config.run_tag or f"run-{uuid4().hex[:10]}"
    return {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": now,
        "updated_at": now,
        "status": "initialized",
        "mode": config.mode,
        "goal": config.goal,
        "metric": {
            "name": config.metric,
            "direction": config.direction,
            "baseline": decimal_to_json(baseline_metric),
            "best": decimal_to_json(baseline_metric),
            "latest": decimal_to_json(baseline_metric),
        },
        "verify": config.verify,
        "guard": config.guard,
        "iterations_cap": config.iterations,
        "stop_condition": config.stop_condition,
        "artifact_paths": {
            "results": str(results_path),
            "state": str(state_path),
        },
        "stats": {
            "total_iterations": 0,
            "kept": 0,
            "discarded": 0,
            "needs_human": 0,
            "consecutive_discards": 0,
            "best_iteration": None,
        },
        "flags": {
            "stop_requested": False,
            "needs_human": False,
            "background_active": config.mode == "background",
        },
        "last_iteration": None,
    }


def initialize_run(
    *,
    repo: str | None,
    results_path_value: str | None,
    state_path_value: str | None,
    config: RunConfig,
    fresh_start: bool,
) -> dict[str, Any]:
    results_path = resolve_path(repo, results_path_value, DEFAULT_RESULTS_PATH)
    state_path = resolve_path(repo, state_path_value, DEFAULT_STATE_PATH)

    archived: dict[str, str] = {}
    for path in (results_path, state_path):
        if path.exists() and not fresh_start:
            raise AutoresearchError(
                f"{path} already exists. Use --fresh-start to archive previous artifacts."
            )
        if path.exists() and fresh_start:
            archived_path = archive_existing(path)
            if archived_path:
                archived[path.name] = str(archived_path)

    write_results_header(results_path)
    state = make_state_payload(config, results_path, state_path)
    if archived:
        state["archived_previous"] = archived
    atomic_write_json(state_path, state)
    return state


def append_iteration(
    *,
    repo: str | None,
    results_path_value: str | None,
    state_path_value: str | None,
    decision: str,
    metric_value: str | None,
    verify_status: str,
    guard_status: str,
    hypothesis: str | None,
    change_summary: str,
    labels: list[str] | None,
    note: str | None,
    iteration: int | None,
) -> dict[str, Any]:
    results_path = resolve_path(repo, results_path_value, DEFAULT_RESULTS_PATH)
    state_path = resolve_path(repo, state_path_value, DEFAULT_STATE_PATH)
    state = read_json_file(state_path)

    current_iteration = iteration or (state["stats"]["total_iterations"] + 1)
    metric_decimal = parse_metric(metric_value)
    best_metric = parse_metric(state["metric"]["best"])
    direction = state["metric"]["direction"]
    label_list = labels or []
    now = utc_now()

    row = {
        "timestamp": now,
        "iteration": str(current_iteration),
        "decision": decision,
        "metric_value": metric_value or "",
        "verify_status": verify_status,
        "guard_status": guard_status,
        "hypothesis": hypothesis or "",
        "change_summary": change_summary,
        "labels": ",".join(label_list),
        "note": note or "",
    }
    append_results_row(results_path, row)

    state["updated_at"] = now
    state["status"] = "running"
    state["stats"]["total_iterations"] = current_iteration
    state["metric"]["latest"] = decimal_to_json(metric_decimal)

    if decision == "keep":
        state["stats"]["kept"] += 1
        state["stats"]["consecutive_discards"] = 0
        if metric_decimal is not None and metric_is_better(metric_decimal, best_metric, direction):
            state["metric"]["best"] = decimal_to_json(metric_decimal)
            state["stats"]["best_iteration"] = current_iteration
    elif decision == "discard":
        state["stats"]["discarded"] += 1
        state["stats"]["consecutive_discards"] += 1
    elif decision == "needs_human":
        state["stats"]["needs_human"] += 1
        state["flags"]["needs_human"] = True
    else:
        raise AutoresearchError(f"Unsupported decision: {decision}")

    state["last_iteration"] = {
        "iteration": current_iteration,
        "decision": decision,
        "metric_value": metric_value,
        "change_summary": change_summary,
        "labels": label_list,
        "timestamp": now,
    }

    atomic_write_json(state_path, state)
    return state


def build_supervisor_snapshot(
    *,
    repo: str | None,
    results_path_value: str | None,
    state_path_value: str | None,
) -> dict[str, Any]:
    results_path = resolve_path(repo, results_path_value, DEFAULT_RESULTS_PATH)
    state_path = resolve_path(repo, state_path_value, DEFAULT_STATE_PATH)
    state = read_json_file(state_path)
    rows = read_results_rows(results_path)

    decision = "relaunch"
    reason = "ready_for_next_iteration"

    if state["flags"]["stop_requested"]:
        decision = "stop"
        reason = "stop_requested"
    elif state["flags"]["needs_human"]:
        decision = "needs_human"
        reason = "human_input_required"
    elif state.get("iterations_cap") is not None and state["stats"]["total_iterations"] >= state["iterations_cap"]:
        decision = "stop"
        reason = "iteration_cap_reached"
    elif state["status"] in {"completed", "stopped"}:
        decision = "stop"
        reason = f"state_{state['status']}"

    snapshot = {
        "decision": decision,
        "reason": reason,
        "run_id": state["run_id"],
        "status": state["status"],
        "mode": state["mode"],
        "goal": state["goal"],
        "metric": state["metric"],
        "stats": state["stats"],
        "last_iteration": state["last_iteration"],
        "results_rows": len(rows),
        "artifact_paths": state["artifact_paths"],
        "flags": state["flags"],
    }
    return snapshot


def write_launch_manifest(
    *,
    repo: str | None,
    launch_path_value: str | None,
    config: RunConfig,
    results_path_value: str | None,
    state_path_value: str | None,
) -> dict[str, Any]:
    launch_path = resolve_path(repo, launch_path_value, DEFAULT_LAUNCH_PATH)
    state_path = resolve_path(repo, state_path_value, DEFAULT_STATE_PATH)
    results_path = resolve_path(repo, results_path_value, DEFAULT_RESULTS_PATH)
    payload = {
        "schema_version": 1,
        "written_at": utc_now(),
        "repo": str(resolve_repo(repo)),
        "mode": "background",
        "goal": config.goal,
        "metric": config.metric,
        "direction": config.direction,
        "verify": config.verify,
        "guard": config.guard,
        "iterations_cap": config.iterations,
        "stop_condition": config.stop_condition,
        "run_tag": config.run_tag,
        "artifact_paths": {
            "results": str(results_path),
            "state": str(state_path),
            "launch": str(launch_path),
        },
    }
    atomic_write_json(launch_path, payload)
    return payload


def set_stop_requested(
    *,
    repo: str | None,
    state_path_value: str | None,
) -> dict[str, Any]:
    state_path = resolve_path(repo, state_path_value, DEFAULT_STATE_PATH)
    state = read_json_file(state_path)
    state["updated_at"] = utc_now()
    state["flags"]["stop_requested"] = True
    state["flags"]["background_active"] = False
    state["status"] = "stopping"
    atomic_write_json(state_path, state)
    return state


def mark_background_active(
    *,
    repo: str | None,
    state_path_value: str | None,
    active: bool,
) -> dict[str, Any]:
    state_path = resolve_path(repo, state_path_value, DEFAULT_STATE_PATH)
    state = read_json_file(state_path)
    state["updated_at"] = utc_now()
    state["flags"]["background_active"] = active
    state["status"] = "running" if active else state["status"]
    atomic_write_json(state_path, state)
    return state


def resume_background_run(
    *,
    repo: str | None,
    state_path_value: str | None,
) -> dict[str, Any]:
    state_path = resolve_path(repo, state_path_value, DEFAULT_STATE_PATH)
    state = read_json_file(state_path)
    if state["mode"] != "background":
        raise AutoresearchError("Only background runs can be resumed.")

    state["updated_at"] = utc_now()
    state["flags"]["stop_requested"] = False
    state["flags"]["background_active"] = True
    if state["status"] in {"stopping", "stopped", "initialized"}:
        state["status"] = "running"
    atomic_write_json(state_path, state)
    return state


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def serialize_dataclass(instance: Any) -> dict[str, Any]:
    return asdict(instance)
