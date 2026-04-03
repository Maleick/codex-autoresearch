from __future__ import annotations

import csv
import json
import hashlib
import re
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import uuid4

try:
    from scripts.autoresearch_subagent_plan import build_subagent_pool_plan
except ModuleNotFoundError:
    from autoresearch_subagent_plan import build_subagent_pool_plan


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
DEFAULT_REPORT_PATH = "autoresearch-report.md"
DEFAULT_SELF_IMPROVEMENT_PATH = "autoresearch-self-improvement.md"
DEFAULT_MEMORY_PATH = "autoresearch-memory.md"
ALLOWED_RESULT_STATUSES = {"pass", "fail", "skip"}
DURATION_TOKEN_RE = re.compile(r"(\d+)([smhd])")
HARDENING_CHECKPOINT_INTERVAL = 10
ESCALATION_WINDOW_SIZE = 10
ESCALATION_REFINE_THRESHOLD = 3
ESCALATION_PIVOT_THRESHOLD = 5
ESCALATION_WEB_PIVOT_THRESHOLD = 2
ESCALATION_HARD_STOP_PIVOTS = 3
ESCALATION_ACTION_LABELS = {"refine": "REFINE", "pivot": "PIVOT", "web": "WEB"}
PUBLIC_RESEARCH_HARVEST = [
    {
        "repo": "microsoft/autogen",
        "url": "https://github.com/microsoft/autogen",
        "adopted_patterns": [
            "explicit multi-agent orchestration",
            "tool iteration caps and handoffs",
            "guarded autonomous workflows",
        ],
        "rejected_patterns": [
            "framework-specific runtime coupling",
        ],
        "rationale": "Adopt multi-agent role separation and bounded tool loops, but keep this skill file-format driven instead of framework-bound.",
    },
    {
        "repo": "OpenHands/OpenHands",
        "url": "https://github.com/OpenHands/OpenHands",
        "adopted_patterns": [
            "agentic development workflow",
            "scale-out subagent execution model",
            "SDK/CLI separation for runtime control",
        ],
        "rejected_patterns": [
            "product-surface complexity beyond this skill bundle",
        ],
        "rationale": "Adopt explicit agent routing and throughput-oriented execution profiles without inheriting the full product stack.",
    },
    {
        "repo": "SWE-agent/SWE-agent",
        "url": "https://github.com/SWE-agent/SWE-agent",
        "adopted_patterns": [
            "tight issue-to-fix iteration loops",
            "verification-first keep/discard discipline",
            "trajectory-style evidence preservation",
        ],
        "rejected_patterns": [
            "benchmark-specific trajectory machinery",
        ],
        "rationale": "Adopt strict experiment accounting and verification gates, but keep our lighter TSV/state artifact scheme.",
    },
    {
        "repo": "openai/openai-agents-python",
        "url": "https://github.com/openai/openai-agents-python",
        "adopted_patterns": [
            "guardrails and human-in-the-loop hooks",
            "session continuity and tracing concepts",
            "delegation through explicit handoffs",
        ],
        "rejected_patterns": [
            "SDK-specific runtime abstractions",
        ],
        "rationale": "Adopt continuity, guardrails, and human-review checkpoints while keeping the plugin runtime transport-agnostic.",
    },
    {
        "repo": "langchain-ai/open_deep_research",
        "url": "https://github.com/langchain-ai/open_deep_research",
        "adopted_patterns": [
            "research-harvest output with cited sources",
            "configurable search/provider pipeline",
            "evaluation-oriented reporting",
        ],
        "rejected_patterns": [
            "heavy benchmark and provider configuration in core state",
        ],
        "rationale": "Adopt explicit public-research harvesting and evaluation framing, but keep runtime state compact and backward-compatible.",
    },
]


class AutoresearchError(RuntimeError):
    pass


@dataclass
class RunConfig:
    goal: str
    metric: str
    direction: str
    verify: str
    mode: str
    scope: str | None = None
    guard: str | None = None
    iterations: int | None = None
    duration: str | None = None
    memory_path: str | None = None
    required_keep_labels: list[str] | None = None
    required_stop_labels: list[str] | None = None
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
    duration: str | None = None
    memory_path: str | None = None
    required_keep_labels: list[str] | None = None
    required_stop_labels: list[str] | None = None
    stop_condition: str | None = None
    rollback_strategy: str | None = None


def normalize_direction(value: str | None) -> str:
    if value is None:
        return "lower"
    normalized = value.strip().lower()
    if normalized not in {"lower", "higher"}:
        raise AutoresearchError(f"Unsupported direction: {value}")
    return normalized


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


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
    if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists() or (root / "tests").exists():
        return "pytest"
    if (root / "Makefile").exists():
        return "make test"
    if (root / "package.json").exists():
        return "npm test"
    return "<set verify command>"


def infer_guard_command(repo: str | None, verify: str | None) -> str | None:
    root = resolve_repo(repo)
    if not (root / "scripts" / "autoresearch_supervisor_status.py").exists():
        return None
    if not verify:
        return "python scripts/autoresearch_supervisor_status.py"
    if verify.strip() == "python scripts/autoresearch_supervisor_status.py":
        return None
    return "python scripts/autoresearch_supervisor_status.py"


def infer_scope(repo: str | None, override: str | None) -> str:
    if override:
        value = override.strip()
        if value:
            return value
    return resolve_repo(repo).name


def parse_iteration_override(iteration: int | None, total_iterations: int) -> int:
    if iteration is None:
        return total_iterations + 1
    if iteration <= 0:
        raise AutoresearchError(f"Invalid iteration number: {iteration}")
    if iteration <= total_iterations:
        raise AutoresearchError(f"Iteration {iteration} must be greater than current total {total_iterations}")
    return iteration


def validate_iteration_cap(value: int | None) -> int | None:
    if value is None:
        return None
    if value < 1:
        raise AutoresearchError(f"Iteration cap must be >= 1, got {value}")
    return value


def complete_run(
    *,
    repo: str | None,
    state_path_value: str | None,
    expected_mode: str | None = None,
) -> dict[str, Any]:
    state_path = resolve_path(repo, state_path_value, DEFAULT_STATE_PATH)
    state = read_json_file(state_path)
    normalize_state_schema(state)
    if expected_mode is not None and state["mode"] != expected_mode:
        raise AutoresearchError(
            f"Only {expected_mode} runs can be completed with this helper."
        )
    if state["status"] == "completed":
        return state

    state["updated_at"] = utc_now()
    state["status"] = "completed"
    state["flags"]["background_active"] = False
    state["flags"]["needs_human"] = False
    state["flags"]["stop_requested"] = False
    state["flags"]["stop_ready"] = False
    atomic_write_json(state_path, state)
    return state


def build_iteration_analytics(
    state: dict[str, Any],
    *,
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    stats = state.get("stats") or {}
    quality_history = stats.get("evidence_quality_history") or []
    if not isinstance(quality_history, list):
        quality_history = []
    quality_history = [value for value in quality_history if isinstance(value, (int, float))]
    stop_reasons = stats.get("stop_reason_distribution", {})
    if not isinstance(stop_reasons, dict):
        stop_reasons = {}
    escalation = state.get("escalation", {})
    recent_signals = escalation.get("recent_signals") if isinstance(escalation, dict) else []
    if not isinstance(recent_signals, list):
        recent_signals = []
    checkpoints = state.get("hardening_checkpoints", [])
    if not isinstance(checkpoints, list):
        checkpoints = []

    total_rows = len(rows)
    web_usage = int(stats.get("web_research_forced_count", 0))
    web_pivot_rate = round(web_usage / total_rows, 3) if total_rows else 0.0
    evidence_trend = quality_history[-10:]
    evidence_delta = None
    if len(evidence_trend) >= 2:
        evidence_delta = round(evidence_trend[-1] - evidence_trend[0], 3)

    return {
        "evidence_quality_trend": evidence_trend,
        "evidence_quality_delta": evidence_delta,
        "stop_reason_distribution": stop_reasons,
        "escalation_counts": stats.get("escalation_counts", {}),
        "recent_escalation_signals": recent_signals[-ESCALATION_WINDOW_SIZE:],
        "web_pivot_usage_rate": web_pivot_rate,
        "hardening_checkpoint_count": len(checkpoints),
        "latest_hardening_iteration": checkpoints[-1]["iteration"] if checkpoints else None,
    }


def evaluate_continuation_controls(
    state: dict[str, Any],
    *,
    rows: list[dict[str, str]],
) -> tuple[str, str]:
    stats = state.get("stats") or {}
    flags = state.get("flags") or {}
    escalation = state.get("escalation", {})
    recent_signals = escalation.get("recent_signals") if isinstance(escalation, dict) else []
    if not isinstance(recent_signals, list):
        recent_signals = []
    current_action = escalation.get("current_action") if isinstance(escalation, dict) else None

    if flags.get("stop_requested"):
        return "stop", "stop_requested"
    if current_action == "HARD_STOP":
        return "needs_human", "escalation_hard_stop"
    if flags.get("needs_human"):
        return "needs_human", "human_intervention_requested"
    if state["status"] in {"completed", "stopped"}:
        return "stop", f"state_{state['status']}"
    if state.get("deadline_at") and parse_utc_timestamp(utc_now()) >= parse_utc_timestamp(state["deadline_at"]):
        return "stop", "duration_elapsed"
    if state.get("iterations_cap") is not None and state["stats"]["total_iterations"] >= state["iterations_cap"]:
        return "stop", "iteration_cap_reached"

    if rows and state["stats"]["total_iterations"] % HARDENING_CHECKPOINT_INTERVAL == 0:
        last_checkpoint = state.get("hardening_checkpoints", [])
        if not isinstance(last_checkpoint, list) or not last_checkpoint:
            return "relaunch", "hardening_checkpoint_needed"
        if last_checkpoint[-1].get("iteration") != state["stats"]["total_iterations"]:
            return "relaunch", "hardening_checkpoint_needed"

    if current_action == "WEB":
        return "relaunch", "web_search_required"
    if current_action == "PIVOT":
        return "relaunch", "pivot_signal"
    if current_action == "REFINE":
        return "relaunch", "refine_signal"

    return "relaunch", "ready_for_next_iteration"


def normalize_state_schema(state: dict[str, Any]) -> None:
    default_stats = {
        "total_iterations": 0,
        "kept": 0,
        "discarded": 0,
        "needs_human": 0,
        "consecutive_discards": 0,
        "best_iteration": None,
        "evidence_quality_history": [],
        "escalation_consecutive_failures": 0,
        "pivots_without_progress": 0,
        "web_research_forced_count": 0,
        "hardening_checkpoints": 0,
        "hardening_history": [],
        "escalation_counts": {"refine": 0, "pivot": 0, "web": 0, "hard_stop": 0},
        "stop_reason_distribution": {},
        "duplicate_signature_streak": 0,
    }
    stats = state.setdefault("stats", {})
    if not isinstance(stats, dict):
        stats = {}
    for key, value in default_stats.items():
        if key not in stats:
            stats[key] = deepcopy(value)
    state["stats"] = stats

    protocol = state.setdefault("protocol", {})
    if not isinstance(protocol, dict):
        protocol = {}
    protocol.setdefault("fingerprint", "")
    protocol.setdefault("fingerprint_history", [])
    protocol.setdefault("continuity_anchors", [])
    protocol.setdefault("version", "v2")
    state["protocol"] = protocol

    continuation_policy = state.get("continuation_policy")
    if not isinstance(continuation_policy, dict) or not continuation_policy:
        continuation_policy = build_continuation_policy(mode=state.get("mode"))
    continuation_policy.setdefault("hardening_checkpoint_interval", HARDENING_CHECKPOINT_INTERVAL)
    escalation_policy = continuation_policy.setdefault("escalation", {})
    if not isinstance(escalation_policy, dict):
        escalation_policy = {}
    escalation_policy.setdefault("window", ESCALATION_WINDOW_SIZE)
    escalation_policy.setdefault("refine_threshold", ESCALATION_REFINE_THRESHOLD)
    escalation_policy.setdefault("pivot_threshold", ESCALATION_PIVOT_THRESHOLD)
    escalation_policy.setdefault("web_pivot_threshold", ESCALATION_WEB_PIVOT_THRESHOLD)
    escalation_policy.setdefault("hard_stop_pivot_threshold", ESCALATION_HARD_STOP_PIVOTS)
    escalation_policy.setdefault(
        "action_labels",
        list(ESCALATION_ACTION_LABELS.values()),
    )
    continuation_policy["escalation"] = escalation_policy
    continuation_policy.setdefault(
        "stop_conditions",
        ["user_stop", "configured_stop_condition", "needs_human"],
    )
    state["continuation_policy"] = continuation_policy

    state.setdefault("public_research_harvest", build_public_research_harvest_payload())
    state.setdefault("hardening_checkpoints", [])
    state.setdefault("hardening_eligible_iterations", [])
    state.setdefault("escalation", state.get("escalation", {}))
    escalation = state["escalation"]
    if not isinstance(escalation, dict):
        escalation = {}
    escalation.setdefault("recent_signals", [])
    escalation.setdefault("counts", {"refine": 0, "pivot": 0, "web": 0, "hard_stop": 0})
    escalation.setdefault("current_action", None)
    escalation.setdefault("current_reason", None)
    escalation.setdefault("action_history", [])
    state["escalation"] = escalation
    state.setdefault(
        "flags",
        {
            "stop_requested": False,
            "needs_human": False,
            "background_active": state.get("mode") == "background",
            "stop_ready": False,
        },
    )


def complete_background_run(
    *,
    repo: str | None,
    state_path_value: str | None,
) -> dict[str, Any]:
    return complete_run(
        repo=repo,
        state_path_value=state_path_value,
        expected_mode="background",
    )


def complete_foreground_run(
    *,
    repo: str | None,
    state_path_value: str | None,
) -> dict[str, Any]:
    return complete_run(
        repo=repo,
        state_path_value=state_path_value,
        expected_mode="foreground",
    )


def normalize_mode(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized not in {"foreground", "background"}:
        raise AutoresearchError(f"Unsupported mode: {value}")
    return normalized


def normalize_result_status(value: str | None, *, field_name: str) -> str:
    if value is None:
        raise AutoresearchError(f"Unsupported {field_name}: {value}")
    normalized = value.strip().lower()
    if normalized not in ALLOWED_RESULT_STATUSES:
        raise AutoresearchError(f"Unsupported {field_name}: {value}")
    return normalized


def normalize_labels(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        raise AutoresearchError(f"Unsupported labels value: {values!r}")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise AutoresearchError(f"Unsupported label entry: {value!r}")
        for token in value.split(","):
            label = token.strip()
            if label and label not in normalized:
                normalized.append(label)
    return normalized


def build_protocol_fingerprint(
    *,
    goal: str,
    scope: str | None,
    metric: str,
    direction: str,
    mode: str,
) -> str:
    payload = {
        "goal": goal,
        "scope": scope or "",
        "metric": metric,
        "direction": direction,
        "mode": mode,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]


def evidence_quality_score(
    *,
    verify_status: str,
    guard_status: str,
) -> float:
    if verify_status == "pass":
        verify_points = 1.0
    elif verify_status == "skip":
        verify_points = 0.45
    else:
        verify_points = 0.0

    if guard_status == "pass":
        guard_points = 0.9
    elif guard_status == "skip":
        guard_points = 0.25
    else:
        guard_points = 0.0

    return min(1.0, (verify_points + guard_points) / 1.9)


def escalate_event(
    event: str,
    state: dict[str, Any],
) -> None:
    escalation = state.get("escalation") or {}
    if not isinstance(escalation, dict):
        escalation = {}
    signals = list(escalation.get("recent_signals", []))
    signals.append(event)
    if len(signals) > ESCALATION_WINDOW_SIZE:
        signals = signals[-ESCALATION_WINDOW_SIZE:]
    escalation["recent_signals"] = signals
    counts = escalation.setdefault("counts", {})
    for key in ("refine", "pivot", "web", "hard_stop"):
        if key not in counts:
            counts[key] = 0
    counts[event] = counts.get(event, 0) + 1
    escalation["counts"] = counts
    stats = state.setdefault("stats", {})
    if not isinstance(stats, dict):
        stats = {}
    escalation_counts = stats.setdefault("escalation_counts", {"refine": 0, "pivot": 0, "web": 0, "hard_stop": 0})
    if not isinstance(escalation_counts, dict):
        escalation_counts = {"refine": 0, "pivot": 0, "web": 0, "hard_stop": 0}
    escalation_counts[event] = counts[event]
    stats["escalation_counts"] = escalation_counts
    state["stats"] = stats
    state["escalation"] = escalation


def count_recent_signals(signals: list[str], target: str) -> int:
    return sum(1 for value in signals[-ESCALATION_WINDOW_SIZE:] if value == target)


def record_escalation_action(
    *,
    state: dict[str, Any],
    iteration: int,
    action: str,
    reason: str,
    timestamp: str,
) -> None:
    normalized = action.lower()
    if normalized == "web_search":
        normalized = "web"
    if normalized == "hard_stop":
        normalized = "hard_stop"
    if normalized not in {"refine", "pivot", "web", "hard_stop"}:
        raise AutoresearchError(f"Unsupported escalation action: {action}")

    escalate_event(normalized, state)
    escalation = state.setdefault("escalation", {})
    if not isinstance(escalation, dict):
        escalation = {}
    history = escalation.setdefault("action_history", [])
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "iteration": iteration,
            "action": ESCALATION_ACTION_LABELS.get(normalized, normalized.upper()),
            "reason": reason,
            "timestamp": timestamp,
        }
    )
    if len(history) > 20:
        history = history[-20:]
    escalation["action_history"] = history
    escalation["current_action"] = ESCALATION_ACTION_LABELS.get(normalized, normalized.upper())
    escalation["current_reason"] = reason
    state["escalation"] = escalation


def build_public_research_harvest_payload() -> list[dict[str, Any]]:
    return [
        {
            "repo": item["repo"],
            "url": item["url"],
            "adopted_patterns": item["adopted_patterns"],
            "rejected_patterns": item["rejected_patterns"],
            "rationale": item["rationale"],
            "adoption_summary": (
                "Adopted "
                + ", ".join(item["adopted_patterns"][:2])
                + "; rejected: "
                + ", ".join(item["rejected_patterns"] or ["none"])
            ),
        }
        for item in PUBLIC_RESEARCH_HARVEST
    ]


def build_iterationality_summary(state: dict[str, Any]) -> dict[str, Any]:
    stats = state.get("stats") or {}
    escalation = state.get("escalation") or {}
    recent_signals = escalation.get("recent_signals", [])
    if not isinstance(recent_signals, list):
        recent_signals = []
    return {
        "evidence_quality_last_10": stats.get("evidence_quality_history", [])[-10:],
        "refine_triggers_last_window": count_recent_signals(recent_signals, "refine"),
        "pivot_triggers_last_window": count_recent_signals(recent_signals, "pivot"),
        "current_action": escalation.get("current_action"),
        "current_reason": escalation.get("current_reason"),
    }

def missing_required_labels(labels: list[str], required_labels: list[str]) -> list[str]:
    label_set = set(labels)
    return [label for label in required_labels if label not in label_set]


def parse_duration_seconds(value: str | None) -> int | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized.isdigit():
        total = int(normalized)
        if total <= 0:
            raise AutoresearchError(f"Invalid duration: {value}")
        return total

    total = 0
    position = 0
    for match in DURATION_TOKEN_RE.finditer(normalized):
        if match.start() != position:
            raise AutoresearchError(f"Invalid duration: {value}")
        amount = int(match.group(1))
        unit = match.group(2)
        multiplier = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
        total += amount * multiplier
        position = match.end()

    if position != len(normalized) or total <= 0:
        raise AutoresearchError(f"Invalid duration: {value}")
    return total


def load_memory_baseline(repo: str | None, memory_path_value: str | None) -> dict[str, Any]:
    memory_path = resolve_path(repo, memory_path_value, DEFAULT_MEMORY_PATH)
    if not memory_path.exists():
        return {
            "path": str(memory_path),
            "loaded": False,
            "excerpt": None,
        }

    text = memory_path.read_text(encoding="utf-8").strip()
    excerpt_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        excerpt_lines.append(stripped)
        if len(excerpt_lines) == 3:
            break
    excerpt = " ".join(excerpt_lines)
    if len(excerpt) > 280:
        excerpt = excerpt[:277].rstrip() + "..."
    return {
        "path": str(memory_path),
        "loaded": True,
        "excerpt": excerpt or None,
    }


def build_continuation_policy(*, mode: str | None) -> dict[str, Any]:
    return {
        "approval_boundary": "pre_launch",
        "post_launch_default": "continue",
        "completion_requires_review": mode == "foreground",
        "hardening_checkpoint_interval": HARDENING_CHECKPOINT_INTERVAL,
        "max_parallel_profile": "max_parallelism" if mode == "background" else "balanced",
        "escalation": {
            "window": ESCALATION_WINDOW_SIZE,
            "refine_threshold": ESCALATION_REFINE_THRESHOLD,
            "pivot_threshold": ESCALATION_PIVOT_THRESHOLD,
            "web_pivot_threshold": ESCALATION_WEB_PIVOT_THRESHOLD,
            "hard_stop_pivot_threshold": ESCALATION_HARD_STOP_PIVOTS,
        },
        "stop_conditions": [
            "user_stop",
            "configured_stop_condition",
            "needs_human",
        ],
    }


def ensure_subagent_pool_plan(
    *,
    goal: str,
    scope: str | None,
    mode: str,
    existing: Any = None,
) -> dict[str, Any]:
    if isinstance(existing, dict) and existing.get("kind") == "autoresearch_subagent_pool":
        return existing
    return build_subagent_pool_plan(goal=goal, scope=scope, mode=mode)


def build_subagent_guidance(
    *,
    state: dict[str, Any],
    decision: str,
    reason: str,
    subagent_pool: dict[str, Any],
) -> dict[str, Any]:
    flags = state.get("flags") or {}
    stats = state.get("stats") or {}
    last_iteration = state.get("last_iteration") or {}
    discard_streak = stats.get("consecutive_discards", 0)
    escalation = state.get("escalation", {})
    escalation_signals = escalation.get("recent_signals") if isinstance(escalation, dict) else []
    current_action = escalation.get("current_action") if isinstance(escalation, dict) else None
    escalation_ready_action = "WEB_SEARCH" if current_action == "WEB" else current_action

    if decision == "stop" and reason.startswith("state_"):
        recommended_action = "close_pool"
        guidance_reason = "The run is already terminal, so the standing pool should wind down."
    elif decision in {"stop", "needs_human"} or flags.get("stop_requested") or flags.get("needs_human"):
        recommended_action = "pause_pool"
        guidance_reason = "Do not fan out new work until the stop or blocker condition is resolved."
    elif escalation_ready_action == "HARD_STOP":
        recommended_action = "pause_pool"
        guidance_reason = "Hard-stop escalation triggered. Escalation requires explicit stop-ready review."
    elif escalation_ready_action == "WEB_SEARCH":
        recommended_action = "launch_public_research"
        guidance_reason = "Two pivots were reached without progress; force a public research refresh before continuing."
    elif escalation_ready_action == "PIVOT":
        recommended_action = "refresh_non_orchestrator_roles"
        guidance_reason = "Pivot threshold hit in the escalation window; rotate implementation and validation roles and re-anchor."
    elif escalation_ready_action == "REFINE":
        recommended_action = "narrow_scope_or_retry"
        guidance_reason = "Three refinement signals in the rolling window suggest reranking the iteration hypothesis."
    elif last_iteration.get("signature") and stats.get("duplicate_signature_streak", 0) >= 2:
        recommended_action = "deduplicate_outputs"
        guidance_reason = "Repeated duplicate summaries were detected; ask evidence roles to provide distinct findings."
    elif discard_streak >= 2:
        recommended_action = "refresh_non_orchestrator_roles"
        guidance_reason = "Keep the orchestrator, but refresh or narrow the supporting roles after repeated discards."
    else:
        recommended_action = "reuse_pool"
        guidance_reason = "Reuse the standing pool and re-anchor each role with the latest result before the next iteration."

    return {
        "recommended_action": recommended_action,
        "reason": guidance_reason,
        "pool_key": subagent_pool.get("pool_key"),
        "resource_tier": subagent_pool.get("resource_tier"),
        "recommended_active_role_ids": subagent_pool.get("recommended_active_role_ids", []),
        "reanchor_checklist": subagent_pool.get("reanchor_checklist", []),
        "execution_profile": subagent_pool.get("execution_profile"),
        "intent_routing": subagent_pool.get("role_intent_routing"),
        "dedupe_policy": subagent_pool.get("deduplication"),
        "fallback_policy": subagent_pool.get("fallback_policy"),
        "iteration_assignments": subagent_pool.get("iteration_assignments"),
        "reanchor_with": {
            "goal": state.get("goal"),
            "scope": state.get("scope"),
            "metric": state.get("metric"),
            "last_iteration": last_iteration,
        },
        "escalation": {
            "ready_action": escalation_ready_action,
            "recent_signals": escalation_signals[-ESCALATION_WINDOW_SIZE:] if isinstance(escalation_signals, list) else [],
            "counts": escalation.get("counts", state["stats"].get("escalation_counts", {})),
            "pivots_without_progress": stats.get("pivots_without_progress", 0),
            "current_reason": escalation.get("current_reason"),
        },
    }


def build_subagent_observability(
    *,
    state: dict[str, Any],
    subagent_pool: dict[str, Any],
) -> dict[str, Any]:
    active_role_ids = subagent_pool.get("recommended_active_role_ids", [])
    if not isinstance(active_role_ids, list):
        active_role_ids = []
    role_limit = int(subagent_pool.get("role_limit", len(active_role_ids) or 1))
    execution_profile = subagent_pool.get("execution_profile")
    current_action = (state.get("escalation") or {}).get("current_action")
    discard_streak = int((state.get("stats") or {}).get("consecutive_discards", 0))
    utilization = round(len(active_role_ids) / max(1, role_limit), 3)

    if current_action in {"WEB", "HARD_STOP"} or discard_streak >= 2:
        queue_pressure = "high"
    elif execution_profile == "max_parallelism" or utilization >= 0.8:
        queue_pressure = "elevated"
    else:
        queue_pressure = "normal"

    return {
        "execution_profile": execution_profile,
        "recommended_active_roles": len(active_role_ids),
        "role_limit": role_limit,
        "utilization": utilization,
        "queue_pressure": queue_pressure,
    }


def build_hardening_checkpoint_status(state: dict[str, Any]) -> dict[str, Any]:
    stats = state.get("stats") or {}
    checkpoints = state.get("hardening_checkpoints", [])
    if not isinstance(checkpoints, list):
        checkpoints = []
    interval = int((state.get("continuation_policy") or {}).get("hardening_checkpoint_interval", HARDENING_CHECKPOINT_INTERVAL))
    total_iterations = int(stats.get("total_iterations", 0))
    last_checkpoint = checkpoints[-1] if checkpoints else None
    due_now = total_iterations > 0 and total_iterations % interval == 0
    current_iteration_hardened = bool(
        due_now and isinstance(last_checkpoint, dict) and last_checkpoint.get("iteration") == total_iterations
    )
    next_due = interval if total_iterations == 0 else ((total_iterations // interval) + 1) * interval
    if due_now and current_iteration_hardened:
        status = "passed"
    elif due_now:
        status = "pending"
    else:
        status = "not_due"
    return {
        "status": status,
        "interval": interval,
        "last_checkpoint_iteration": last_checkpoint.get("iteration") if isinstance(last_checkpoint, dict) else None,
        "next_due_iteration": next_due,
        "protocol_fingerprint_match": last_checkpoint.get("protocol_fingerprint_match") if isinstance(last_checkpoint, dict) else None,
    }


def build_setup_summary(*, repo: str | None, config: WizardConfig) -> dict[str, Any]:
    verify = config.verify or infer_verify_command(repo)
    guard = config.guard if config.guard is not None else infer_guard_command(repo, verify)
    if guard == "":
        guard = None
    direction = normalize_direction(config.direction)
    mode = normalize_mode(config.mode)
    duration_seconds = parse_duration_seconds(config.duration)
    required_keep_labels = normalize_labels(config.required_keep_labels)
    required_stop_labels = normalize_labels(config.required_stop_labels)
    memory = load_memory_baseline(repo, config.memory_path)
    stop_reasons = [
        f"`{verify}` reaches the target metric"
        if verify and verify != "<set verify command>"
        else "the target metric is met"
    ]
    if config.iterations is not None:
        stop_reasons.append(f"{config.iterations} iterations complete")
    if config.duration:
        stop_reasons.append(f"{config.duration} elapses")
    if required_stop_labels:
        stop_reasons.append(f"the retained keep includes labels {', '.join(required_stop_labels)}")
    stop_condition = config.stop_condition or f"stop when {' or '.join(stop_reasons)}"
    rollback_strategy = config.rollback_strategy or "discard the current experiment and keep the last verified state"
    metric = config.metric or "primary verify metric"
    scope = infer_scope(repo, config.scope)
    protocol_fingerprint = build_protocol_fingerprint(
        goal=config.goal or "pending autoresearch goal",
        scope=scope,
        metric=metric,
        direction=normalize_direction(config.direction),
        mode=config.mode,
    )
    subagent_pool = build_subagent_pool_plan(
        goal=config.goal or "pending autoresearch goal",
        scope=scope,
        mode=config.mode or "foreground",
    )
    continuation_policy = build_continuation_policy(mode=mode)

    missing_required: list[str] = []
    if not config.goal:
        missing_required.append("goal")
    if not config.mode:
        missing_required.append("mode")
    if not config.scope:
        missing_required.append("scope")
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
    if not config.scope:
        questions.append(
            {
                "id": "scope",
                "prompt": f"What scope should this run cover? Default: `{scope}`",
                "reason": "Scope prevents edits outside the intended boundary.",
            }
        )
    if not config.mode:
        questions.append(
            {
                "id": "mode",
                "prompt": "Should the run stay in `foreground` or move to `background`?",
                "reason": "The skill requires an explicit run-mode choice before launch.",
            }
        )
    if config.mode == "background" and not config.duration:
        questions.append(
            {
                "id": "duration",
                "prompt": "How long should the background run be allowed to continue? Example: `5h` or `300m`.",
                "reason": "An unattended run should have an explicit wall-clock cap.",
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
        "duration": config.duration,
        "duration_seconds": duration_seconds,
        "memory": memory,
        "subagent_pool": subagent_pool,
        "continuation_policy": continuation_policy,
        "required_keep_labels": required_keep_labels,
        "required_stop_labels": required_stop_labels,
        "stop_condition": stop_condition,
        "rollback_strategy": rollback_strategy,
        "missing_required": missing_required,
        "protocol": {
            "version": "v2",
            "fingerprint": protocol_fingerprint,
            "adoption_notes": build_public_research_harvest_payload()[:2],
        },
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


def make_state_payload(
    config: RunConfig,
    results_path: Path,
    state_path: Path,
    *,
    repo: str | None = None,
) -> dict[str, Any]:
    direction = normalize_direction(config.direction)
    baseline_metric = parse_metric(config.baseline)
    now = utc_now()
    duration_seconds = parse_duration_seconds(config.duration)
    required_keep_labels = normalize_labels(config.required_keep_labels)
    required_stop_labels = normalize_labels(config.required_stop_labels)
    memory = load_memory_baseline(repo, config.memory_path)
    protocol_fingerprint = build_protocol_fingerprint(
        goal=config.goal,
        scope=config.scope,
        metric=config.metric,
        direction=direction,
        mode=config.mode,
    )
    public_research_harvest = build_public_research_harvest_payload()
    subagent_pool = build_subagent_pool_plan(
        goal=config.goal,
        scope=config.scope or "current repository",
        mode=config.mode,
    )
    continuation_policy = build_continuation_policy(mode=config.mode)
    deadline_at = (
        (parse_utc_timestamp(now) + timedelta(seconds=duration_seconds)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        if duration_seconds is not None
        else None
    )
    run_id = config.run_tag or f"run-{uuid4().hex[:10]}"
    return {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": now,
        "updated_at": now,
        "status": "initialized",
        "protocol": {
            "version": "v2",
            "fingerprint": protocol_fingerprint,
            "fingerprint_history": [protocol_fingerprint],
            "continuity_anchors": [
                {
                    "type": "scope",
                    "value": (config.scope or "current repository"),
                },
                {
                    "type": "mode",
                    "value": config.mode,
                },
                {
                    "type": "metric_direction",
                    "value": direction,
                },
            ],
        },
        "public_research_harvest": public_research_harvest,
        "hardening_checkpoints": [],
        "hardening_eligible_iterations": [],
        "mode": config.mode,
        "goal": config.goal,
        "scope": config.scope or "current repository",
        "metric": {
            "name": config.metric,
            "direction": direction,
            "baseline": decimal_to_json(baseline_metric),
            "best": decimal_to_json(baseline_metric),
            "latest": decimal_to_json(baseline_metric),
        },
        "verify": config.verify,
        "guard": config.guard,
        "iterations_cap": config.iterations,
        "duration": config.duration,
        "duration_seconds": duration_seconds,
        "deadline_at": deadline_at,
        "memory": memory,
        "subagent_pool": subagent_pool,
        "continuation_policy": continuation_policy,
        "label_requirements": {
            "keep": required_keep_labels,
            "stop": required_stop_labels,
        },
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
            "evidence_quality_history": [],
            "escalation_consecutive_failures": 0,
            "pivots_without_progress": 0,
            "web_research_forced_count": 0,
            "hardening_checkpoints": 0,
            "escalation_counts": {
                "refine": 0,
                "pivot": 0,
                "web": 0,
                "hard_stop": 0,
            },
            "stop_reason_distribution": {},
            "duplicate_signature_streak": 0,
        },
        "flags": {
            "stop_requested": False,
            "needs_human": False,
            "background_active": config.mode == "background",
            "stop_ready": False,
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
    config.iterations = validate_iteration_cap(config.iterations)
    config.direction = normalize_direction(config.direction)

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
    state = make_state_payload(config, results_path, state_path, repo=repo)
    normalize_state_schema(state)
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
    normalize_state_schema(state)

    current_iteration = parse_iteration_override(iteration, state["stats"]["total_iterations"])
    metric_decimal = parse_metric(metric_value)
    best_metric = parse_metric(state["metric"]["best"])
    direction = state["metric"]["direction"]
    verify_status = normalize_result_status(verify_status, field_name="verify_status")
    guard_status = normalize_result_status(guard_status, field_name="guard_status")
    label_list = normalize_labels(labels)
    label_requirements = state.get("label_requirements", {})
    required_keep_labels = normalize_labels(label_requirements.get("keep"))
    required_stop_labels = normalize_labels(label_requirements.get("stop"))
    missing_keep_labels = missing_required_labels(label_list, required_keep_labels)
    missing_stop_labels = missing_required_labels(label_list, required_stop_labels)
    keep_labels_satisfied = not missing_keep_labels
    stop_labels_satisfied = not missing_stop_labels
    if decision == "keep" and missing_keep_labels:
        raise AutoresearchError("Keep decision requires labels: " + ", ".join(missing_keep_labels))
    now = utc_now()
    previous_recent_signals = list(state.get("escalation", {}).get("recent_signals", []))
    if not isinstance(previous_recent_signals, list):
        previous_recent_signals = []
    previous_refine_count = count_recent_signals(previous_recent_signals, "refine")
    previous_consecutive_failures = int(state["stats"].get("escalation_consecutive_failures", 0))
    previous_pivots_without_progress = int(state["stats"].get("pivots_without_progress", 0))

    current_signature = hashlib.sha256(
        f"{change_summary}|{hypothesis or ''}|{','.join(sorted(label_list))}".encode("utf-8")
    ).hexdigest()[:16]
    last_iteration = state.get("last_iteration") or {}
    last_signature = last_iteration.get("signature")
    if last_signature and last_signature == current_signature:
        state["stats"]["duplicate_signature_streak"] = int(state["stats"].get("duplicate_signature_streak", 0)) + 1
    else:
        state["stats"]["duplicate_signature_streak"] = 0

    quality = evidence_quality_score(
        verify_status=verify_status,
        guard_status=guard_status,
    )
    quality_history = state["stats"].get("evidence_quality_history") or []
    if not isinstance(quality_history, list):
        quality_history = []
    quality_history.append(quality)
    if len(quality_history) > 20:
        quality_history = quality_history[-20:]
    state["stats"]["evidence_quality_history"] = quality_history

    protocol_fingerprint = build_protocol_fingerprint(
        goal=state["goal"],
        scope=state["scope"],
        metric=state["metric"]["name"],
        direction=state["metric"]["direction"],
        mode=state["mode"],
    )
    protocol = state.setdefault("protocol", {})
    if not isinstance(protocol, dict):
        protocol = {}
    fingerprint_history = protocol.setdefault("fingerprint_history", [])
    if not isinstance(fingerprint_history, list):
        fingerprint_history = []
    fingerprint_history.append(protocol_fingerprint)
    if len(fingerprint_history) > 20:
        fingerprint_history = fingerprint_history[-20:]
    protocol["fingerprint"] = protocol_fingerprint
    protocol["fingerprint_history"] = fingerprint_history
    state["protocol"] = protocol

    state["stats"]["signature"] = state["stats"].get("signature", 0) + 1

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
    state["flags"]["stop_ready"] = decision == "keep" and stop_labels_satisfied

    metric_improved = (
        metric_decimal is not None
        and metric_is_better(metric_decimal, best_metric, direction)
    )
    progress_made = decision == "keep" and metric_improved
    if decision == "keep":
        signal = "keep"
    elif decision == "needs_human" or verify_status == "fail" or guard_status == "fail":
        signal = "pivot"
    else:
        signal = "refine"

    escalation_signals = list(state.get("escalation", {}).get("recent_signals", []))
    if not isinstance(escalation_signals, list):
        escalation_signals = []
    escalation_signals.append(signal)
    if len(escalation_signals) > ESCALATION_WINDOW_SIZE:
        escalation_signals = escalation_signals[-ESCALATION_WINDOW_SIZE:]
    state.setdefault("escalation", {})["recent_signals"] = escalation_signals

    if signal in {"refine", "pivot"}:
        state["stats"]["escalation_consecutive_failures"] = previous_consecutive_failures + 1
    else:
        state["stats"]["escalation_consecutive_failures"] = 0

    if decision == "keep":
        state["stats"]["kept"] += 1
        state["stats"]["consecutive_discards"] = 0
        if metric_improved:
            state["metric"]["best"] = decimal_to_json(metric_decimal)
            state["stats"]["best_iteration"] = current_iteration
    elif decision == "discard":
        state["stats"]["discarded"] += 1
        state["stats"]["consecutive_discards"] += 1
    elif decision == "needs_human":
        state["stats"]["needs_human"] += 1
        state["flags"]["needs_human"] = True
        state["stats"]["consecutive_discards"] = 0
    else:
        raise AutoresearchError(f"Unsupported decision: {decision}")

    emitted_actions: list[str] = []
    refine_count = count_recent_signals(escalation_signals, "refine")
    consecutive_failures = int(state["stats"].get("escalation_consecutive_failures", 0))
    pivots_without_progress = 0 if progress_made else previous_pivots_without_progress
    refine_cycles_before = previous_refine_count // ESCALATION_REFINE_THRESHOLD
    refine_cycles_after = refine_count // ESCALATION_REFINE_THRESHOLD
    pivot_cycles_before = previous_consecutive_failures // ESCALATION_PIVOT_THRESHOLD
    pivot_cycles_after = consecutive_failures // ESCALATION_PIVOT_THRESHOLD

    if refine_cycles_after > refine_cycles_before and refine_count >= ESCALATION_REFINE_THRESHOLD:
        record_escalation_action(
            state=state,
            iteration=current_iteration,
            action="REFINE",
            reason="Three refinement-required signals accumulated in the rolling window.",
            timestamp=now,
        )
        emitted_actions.append("REFINE")

    if pivot_cycles_after > pivot_cycles_before and consecutive_failures >= ESCALATION_PIVOT_THRESHOLD:
        pivots_without_progress += 1
        state["stats"]["pivots_without_progress"] = pivots_without_progress
        record_escalation_action(
            state=state,
            iteration=current_iteration,
            action="PIVOT",
            reason="Five failures or consecutive regressions triggered a strategy pivot.",
            timestamp=now,
        )
        emitted_actions.append("PIVOT")
    else:
        state["stats"]["pivots_without_progress"] = pivots_without_progress

    current_pivots_without_progress = int(state["stats"].get("pivots_without_progress", 0))
    if previous_pivots_without_progress < ESCALATION_WEB_PIVOT_THRESHOLD <= current_pivots_without_progress:
        state["stats"]["web_research_forced_count"] = int(state["stats"].get("web_research_forced_count", 0)) + 1
        record_escalation_action(
            state=state,
            iteration=current_iteration,
            action="WEB_SEARCH",
            reason="Two pivots were triggered without progress; force a public research pass.",
            timestamp=now,
        )
        emitted_actions.append("WEB_SEARCH")
    if previous_pivots_without_progress < ESCALATION_HARD_STOP_PIVOTS <= current_pivots_without_progress:
        state["flags"]["needs_human"] = True
        state["stats"].setdefault("stop_reason_distribution", {})
        state["stats"]["stop_reason_distribution"]["escalation_hard_stop"] = int(
            state["stats"]["stop_reason_distribution"].get("escalation_hard_stop", 0)
        ) + 1
        record_escalation_action(
            state=state,
            iteration=current_iteration,
            action="HARD_STOP",
            reason="Three pivots were triggered without progress; stop for human review.",
            timestamp=now,
        )
        emitted_actions.append("HARD_STOP")

    if not emitted_actions and progress_made:
        state["escalation"]["current_action"] = None
        state["escalation"]["current_reason"] = "progress_restored"

    state["escalation_active"] = bool(
        state["escalation"].get("current_action") in {"WEB", "HARD_STOP"}
        or state["stats"].get("pivots_without_progress", 0) >= ESCALATION_WEB_PIVOT_THRESHOLD
    )

    if state["stats"]["total_iterations"] % HARDENING_CHECKPOINT_INTERVAL == 0:
        continuity_ok = protocol_fingerprint == state["protocol"].get("fingerprint")
        escalation_actions = state.get("escalation", {}).get("recent_signals", [])
        quality_window = state["stats"]["evidence_quality_history"][-10:]
        checkpoint = {
            "iteration": current_iteration,
            "protocol_fingerprint": protocol_fingerprint,
            "protocol_fingerprint_match": continuity_ok,
            "continuity_audit": {
                "duplicate_signature_streak": state["stats"].get("duplicate_signature_streak", 0),
                "latest_action": state["escalation"].get("current_action"),
                "latest_reason": state["escalation"].get("current_reason"),
                "stop_flags_clear": not state["flags"].get("stop_requested"),
            },
            "evidence_quality_avg_10": round(mean(quality_window), 3) if quality_window else None,
            "window_refine_signals": count_recent_signals(escalation_actions, "refine"),
            "window_pivot_signals": count_recent_signals(escalation_actions, "pivot"),
        }
        hardening_history = state["hardening_checkpoints"]
        if not isinstance(hardening_history, list):
            hardening_history = []
        hardening_history.append(checkpoint)
        if len(hardening_history) > 20:
            hardening_history = hardening_history[-20:]
        state["hardening_checkpoints"] = hardening_history
        state["stats"]["hardening_checkpoints"] = len(hardening_history)
        state["hardening_eligible_iterations"] = [h["iteration"] for h in hardening_history]
        state["stats"]["hardening_history"] = hardening_history

    state["last_iteration"] = {
        "iteration": current_iteration,
        "decision": decision,
        "metric_value": metric_value,
        "change_summary": change_summary,
        "labels": label_list,
        "signature": current_signature,
        "timestamp": now,
        "evidence_quality": quality,
        "protocol_fingerprint": protocol_fingerprint,
        "escalation": {
            "signal": signal,
            "actions": emitted_actions,
            "reason": state["escalation"].get("current_reason"),
        },
        "keep_labels_satisfied": keep_labels_satisfied,
        "stop_labels_satisfied": stop_labels_satisfied,
        "missing_keep_labels": missing_keep_labels,
        "missing_stop_labels": missing_stop_labels,
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
    normalize_state_schema(state)
    rows = read_results_rows(results_path)

    decision, reason = evaluate_continuation_controls(state=state, rows=rows)

    subagent_pool = ensure_subagent_pool_plan(
        goal=state.get("goal") or "current autoresearch goal",
        scope=state.get("scope"),
        mode=state.get("mode") or "foreground",
        existing=state.get("subagent_pool"),
    )
    continuation_policy = state.get("continuation_policy")
    if not isinstance(continuation_policy, dict):
        continuation_policy = build_continuation_policy(mode=state.get("mode"))

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
        "label_requirements": state.get("label_requirements", {"keep": [], "stop": []}),
        "subagent_pool": subagent_pool,
        "protocol": state.get("protocol", {}),
        "continuation_policy": continuation_policy,
        "subagent_guidance": build_subagent_guidance(
            state=state,
            decision=decision,
            reason=reason,
            subagent_pool=subagent_pool,
        ),
        "iteration_analytics": build_iteration_analytics(state=state, rows=rows),
        "iterationality_summary": build_iterationality_summary(state),
        "hardening_checkpoint_status": build_hardening_checkpoint_status(state),
        "subagent_observability": build_subagent_observability(state=state, subagent_pool=subagent_pool),
        "hardening_checkpoints": state.get("hardening_checkpoints", []),
        "public_research_harvest": state.get("public_research_harvest", build_public_research_harvest_payload()),
    }
    return snapshot


def build_launch_manifest_payload(
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
    subagent_pool = build_subagent_pool_plan(
        goal=config.goal,
        scope=config.scope or "current repository",
        mode=config.mode,
    )
    continuation_policy = build_continuation_policy(mode=config.mode)
    return {
        "schema_version": 1,
        "written_at": utc_now(),
        "repo": str(resolve_repo(repo)),
        "mode": "background",
        "goal": config.goal,
        "scope": config.scope or "current repository",
        "metric": config.metric,
        "direction": config.direction,
        "verify": config.verify,
        "guard": config.guard,
        "iterations_cap": config.iterations,
        "duration": config.duration,
        "duration_seconds": parse_duration_seconds(config.duration),
        "memory": load_memory_baseline(repo, config.memory_path),
        "subagent_pool": subagent_pool,
        "continuation_policy": continuation_policy,
        "required_keep_labels": normalize_labels(config.required_keep_labels),
        "required_stop_labels": normalize_labels(config.required_stop_labels),
        "stop_condition": config.stop_condition,
        "run_tag": config.run_tag,
        "artifact_paths": {
            "results": str(results_path),
            "state": str(state_path),
            "launch": str(launch_path),
        },
    }


def write_launch_manifest(
    *,
    repo: str | None,
    launch_path_value: str | None,
    config: RunConfig,
    results_path_value: str | None,
    state_path_value: str | None,
    fresh_start: bool = False,
) -> dict[str, Any]:
    launch_path = resolve_path(repo, launch_path_value, DEFAULT_LAUNCH_PATH)
    if launch_path.exists() and not fresh_start:
        raise AutoresearchError(
            f"{launch_path} already exists. Use --fresh-start to archive previous artifacts."
        )
    if launch_path.exists() and fresh_start:
        archive_existing(launch_path)
    payload = build_launch_manifest_payload(
        repo=repo,
        launch_path_value=launch_path_value,
        config=config,
        results_path_value=results_path_value,
        state_path_value=state_path_value,
    )
    atomic_write_json(launch_path, payload)
    return payload


def set_stop_requested(
    *,
    repo: str | None,
    state_path_value: str | None,
) -> dict[str, Any]:
    state_path = resolve_path(repo, state_path_value, DEFAULT_STATE_PATH)
    state = read_json_file(state_path)
    normalize_state_schema(state)
    if state["mode"] != "background":
        raise AutoresearchError("Only background runs can be stopped with background controls.")
    state["updated_at"] = utc_now()
    state["flags"]["stop_requested"] = True
    state["flags"]["background_active"] = False
    state["status"] = "stopping"
    state["stats"]["stop_reason_distribution"]["stop_requested"] = int(
        state["stats"]["stop_reason_distribution"].get("stop_requested", 0)
    ) + 1
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
    normalize_state_schema(state)
    if state["mode"] != "background":
        raise AutoresearchError("Only background runs can be managed with background controls.")
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
    normalize_state_schema(state)
    if state["mode"] != "background":
        raise AutoresearchError("Only background runs can be resumed.")
    if state["status"] == "completed":
        raise AutoresearchError("Completed runs cannot be resumed.")

    state["updated_at"] = utc_now()
    state["flags"]["stop_requested"] = False
    state["flags"]["needs_human"] = False
    state["flags"]["background_active"] = True
    state["status"] = "running"
    state["escalation"]["current_action"] = None
    state["escalation"]["current_reason"] = "resumed"
    atomic_write_json(state_path, state)
    return state


def build_run_report(
    *,
    repo: str | None,
    results_path_value: str | None,
    state_path_value: str | None,
) -> str:
    state_path = resolve_path(repo, state_path_value, DEFAULT_STATE_PATH)
    state = read_json_file(state_path)
    normalize_state_schema(state)
    rows = read_results_rows(resolve_path(repo, results_path_value, DEFAULT_RESULTS_PATH))
    label_requirements = state.get("label_requirements", {"keep": [], "stop": []})
    last_iteration = state.get("last_iteration") or {}
    memory = state.get("memory") or {"path": None, "loaded": False, "excerpt": None}
    analytics = build_iteration_analytics(state=state, rows=rows)
    hardening_status = build_hardening_checkpoint_status(state)
    lines = [
        "# Autoresearch Report",
        "",
        f"- Run ID: `{state['run_id']}`",
        f"- Status: `{state['status']}`",
        f"- Mode: `{state['mode']}`",
        f"- Goal: {state['goal']}",
        f"- Metric: `{state['metric']['name']}` ({state['metric']['direction']})",
        f"- Best metric: `{state['metric']['best']}`",
        f"- Latest metric: `{state['metric']['latest']}`",
        f"- Iterations: `{state['stats']['total_iterations']}`",
        f"- Kept: `{state['stats']['kept']}`",
        f"- Discarded: `{state['stats']['discarded']}`",
        f"- Needs human: `{state['stats']['needs_human']}`",
        f"- Iteration cap: `{state.get('iterations_cap')}`",
        f"- Duration: `{state.get('duration')}`",
        f"- Deadline: `{state.get('deadline_at')}`",
        f"- Memory loaded: `{memory.get('loaded')}`",
        f"- Memory path: `{memory.get('path')}`",
        f"- Memory excerpt: {memory.get('excerpt') or 'none'}",
        f"- Stop ready: `{state['flags'].get('stop_ready')}`",
        f"- Protocol fingerprint: `{state.get('protocol', {}).get('fingerprint')}`",
        f"- Escalation state: `{state.get('escalation', {}).get('current_action') or 'none'}`",
        f"- Escalation signals (last 10): `{state.get('escalation', {}).get('recent_signals', [])[-10:]}`",
        f"- Evidence quality trend: `{analytics.get('evidence_quality_trend')}`",
        f"- Web pivot usage rate: `{analytics.get('web_pivot_usage_rate')}`",
        f"- Hardening checkpoint status: `{hardening_status.get('status')}`",
        f"- Queue pressure: `{build_subagent_observability(state=state, subagent_pool=state.get('subagent_pool', {})).get('queue_pressure')}`",
        "",
        "## Label gates",
        "",
        f"- Required keep labels: `{', '.join(label_requirements.get('keep', [])) or 'none'}`",
        f"- Required stop labels: `{', '.join(label_requirements.get('stop', [])) or 'none'}`",
        "",
        "## Last iteration",
        "",
        f"- Iteration: `{last_iteration.get('iteration')}`",
        f"- Decision: `{last_iteration.get('decision')}`",
        f"- Labels: `{', '.join(last_iteration.get('labels', [])) or 'none'}`",
        f"- Keep labels satisfied: `{last_iteration.get('keep_labels_satisfied')}`",
        f"- Stop labels satisfied: `{last_iteration.get('stop_labels_satisfied')}`",
        f"- Missing keep labels: `{', '.join(last_iteration.get('missing_keep_labels', [])) or 'none'}`",
        f"- Missing stop labels: `{', '.join(last_iteration.get('missing_stop_labels', [])) or 'none'}`",
        f"- Change summary: {last_iteration.get('change_summary')}",
        "",
        "## Recent iterations",
        "",
        "| Iteration | Decision | Metric | Labels | Summary |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows[-5:]:
        lines.append(
            f"| {row.get('iteration', '')} | {row.get('decision', '')} | {row.get('metric_value', '')} | "
            f"{row.get('labels', '') or 'none'} | {row.get('change_summary', '')} |"
        )
    if not rows:
        lines.append("| none | none | none | none | no iterations recorded yet |")
    lines.extend(
        [
            "",
            "## Public Research Harvest",
            "| Repository | Adopted patterns | Rejected / Not adopted patterns | Rationale |",
            "| --- | --- | --- | --- |",
        ]
    )
    for entry in state.get("public_research_harvest", build_public_research_harvest_payload()):
        lines.append(
            f"| {entry['repo']} | {', '.join(entry['adopted_patterns']) or 'none'} "
            f"| {', '.join(entry['rejected_patterns']) or 'none'} | {entry.get('rationale', 'none')} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_run_report(
    *,
    repo: str | None,
    results_path_value: str | None,
    state_path_value: str | None,
    report_path_value: str | None,
) -> Path:
    report_path = resolve_path(repo, report_path_value, DEFAULT_REPORT_PATH)
    atomic_write_text(
        report_path,
        build_run_report(
            repo=repo,
            results_path_value=results_path_value,
            state_path_value=state_path_value,
        ),
    )
    return report_path


def build_self_improvement_payload(
    *,
    repo: str | None,
    results_path_value: str | None,
    state_path_value: str | None,
) -> dict[str, Any]:
    state_path = resolve_path(repo, state_path_value, DEFAULT_STATE_PATH)
    state = read_json_file(state_path)
    normalize_state_schema(state)
    rows = read_results_rows(resolve_path(repo, results_path_value, DEFAULT_RESULTS_PATH))
    last_iteration = state.get("last_iteration") or {}
    latest_row = rows[-1] if rows else {}
    label_requirements = state.get("label_requirements") or {"keep": [], "stop": []}
    memory = state.get("memory") or {"path": None, "loaded": False, "excerpt": None}

    keep_recommendations: list[str] = []
    change_recommendations: list[str] = []
    next_run_defaults: list[str] = []

    decision = last_iteration.get("decision")
    verify_status = latest_row.get("verify_status")
    guard_status = latest_row.get("guard_status")
    required_keep_labels = label_requirements.get("keep", [])
    required_stop_labels = label_requirements.get("stop", [])
    missing_keep_labels = last_iteration.get("missing_keep_labels") or []
    missing_stop_labels = last_iteration.get("missing_stop_labels") or []

    if decision == "keep":
        keep_recommendations.append(
            "Keep the current direction of change; the latest iteration was retained."
        )
    elif decision:
        change_recommendations.append(
            "Require a clearer improvement delta before retaining the next iteration."
        )

    if verify_status == "pass":
        keep_recommendations.append(
            "Keep the current verify command shape; it passed on the latest recorded iteration."
        )
    elif verify_status == "fail":
        change_recommendations.append(
            "Tighten or simplify the verify command before the next unattended run."
        )
    elif verify_status == "skip":
        change_recommendations.append(
            "Avoid skipped verification on the next run; make the verify step mechanically executable."
        )

    if guard_status == "pass":
        keep_recommendations.append(
            "Keep the current guard command or review gate; it passed on the latest recorded iteration."
        )
    elif guard_status == "fail":
        change_recommendations.append(
            "Strengthen the guard command or narrow the run scope before the next unattended run."
        )
    elif guard_status == "skip" and state.get("guard"):
        change_recommendations.append(
            "Do not skip the configured guard command on the next unattended run."
        )

    if required_keep_labels:
        if missing_keep_labels:
            change_recommendations.append(
                "Do not retain future iterations until these keep labels are recorded: "
                + ", ".join(missing_keep_labels)
                + "."
            )
        else:
            keep_recommendations.append(
                "Carry forward the required keep labels: "
                + ", ".join(required_keep_labels)
                + "."
            )

    if required_stop_labels:
        if missing_stop_labels:
            change_recommendations.append(
                "Do not treat the run as stop-ready until these stop labels are recorded: "
                + ", ".join(missing_stop_labels)
                + "."
            )
        else:
            keep_recommendations.append(
                "Carry forward the required stop labels: "
                + ", ".join(required_stop_labels)
                + "."
            )

    if state["stats"]["needs_human"] > 0:
        change_recommendations.append(
            "Add an earlier escalation checkpoint or reduce scope before the next unattended run."
        )

    if state["stats"]["discarded"] > state["stats"]["kept"]:
        change_recommendations.append(
            "Reduce the next run's scope or shorten the experiment loop; this run discarded more iterations than it kept."
        )

    if state.get("iterations_cap") is not None:
        next_run_defaults.append(f"Iterations cap: {state['iterations_cap']}")
    if state.get("duration"):
        next_run_defaults.append(f"Duration budget: {state['duration']}")
    if required_keep_labels:
        next_run_defaults.append("Required keep labels: " + ", ".join(required_keep_labels))
    if required_stop_labels:
        next_run_defaults.append("Required stop labels: " + ", ".join(required_stop_labels))
    if state.get("verify"):
        next_run_defaults.append(f"Verify command: {state['verify']}")
    if state.get("guard"):
        next_run_defaults.append(f"Guard command: {state['guard']}")
    if memory.get("loaded") and memory.get("path"):
        next_run_defaults.append(f"Memory baseline: {memory['path']}")

    summary = (
        f"Run `{state['run_id']}` completed after `{state['stats']['total_iterations']}` iterations. "
        "Use these learned defaults as the starting baseline for the next autoresearch cycle."
    )
    return {
        "run_id": state["run_id"],
        "summary": summary,
        "iteration_analytics": build_iteration_analytics(state=state, rows=rows),
        "hardening_checkpoint_status": build_hardening_checkpoint_status(state),
        "keep_recommendations": keep_recommendations,
        "change_recommendations": change_recommendations,
        "next_run_defaults": next_run_defaults,
        "public_research_harvest": state.get("public_research_harvest", build_public_research_harvest_payload()),
    }


def build_self_improvement_report(
    *,
    repo: str | None,
    results_path_value: str | None,
    state_path_value: str | None,
) -> str:
    payload = build_self_improvement_payload(
        repo=repo,
        results_path_value=results_path_value,
        state_path_value=state_path_value,
    )
    lines = [
        "# Autoresearch Self-Improvement",
        "",
        payload["summary"],
        "",
        "## Keep",
    ]
    if payload["keep_recommendations"]:
        lines.extend(f"- {item}" for item in payload["keep_recommendations"])
    else:
        lines.append("- No keep recommendations were extracted from the latest run.")
    lines.extend(["", "## Change"])
    if payload["change_recommendations"]:
        lines.extend(f"- {item}" for item in payload["change_recommendations"])
    else:
        lines.append("- No change recommendations were extracted from the latest run.")
    lines.extend(["", "## Recommended next run defaults"])
    if payload["next_run_defaults"]:
        lines.extend(f"- {item}" for item in payload["next_run_defaults"])
    else:
        lines.append("- No next-run defaults were recorded.")
    lines.extend(["", "## Iteration evidence trend", f"- Trend (last 10): {payload['iteration_analytics'].get('evidence_quality_trend', [])}"])
    lines.append(f"- Hardening checkpoint status: {payload['hardening_checkpoint_status'].get('status')}")
    lines.extend(
        [
            "",
            "## Public research harvest for this run",
            "| Repository | Adopted patterns | Rejected / Not adopted patterns | Rationale |",
            "| --- | --- | --- | --- |",
        ]
    )
    for entry in payload["public_research_harvest"]:
        lines.append(
            f"| {entry['repo']} | {', '.join(entry['adopted_patterns']) or 'none'} "
            f"| {', '.join(entry['rejected_patterns']) or 'none'} | {entry.get('rationale', 'none')} |"
        )
    lines.extend(
        [
            "",
            "## Reuse rule",
            "- Load `autoresearch-memory.md` before the next run and treat it as the default baseline.",
            "",
        ]
    )
    return "\n".join(lines)


def build_memory_file(
    *,
    repo: str | None,
    results_path_value: str | None,
    state_path_value: str | None,
) -> str:
    payload = build_self_improvement_payload(
        repo=repo,
        results_path_value=results_path_value,
        state_path_value=state_path_value,
    )
    lines = [
        "# Autoresearch Memory",
        "",
        "Carry these learnings into the next run unless the operator overrides them.",
        "",
        "## Keep",
    ]
    if payload["keep_recommendations"]:
        lines.extend(f"- {item}" for item in payload["keep_recommendations"])
    else:
        lines.append("- No keep recommendations were extracted from the latest run.")
    lines.extend(["", "## Change"])
    if payload["change_recommendations"]:
        lines.extend(f"- {item}" for item in payload["change_recommendations"])
    else:
        lines.append("- No change recommendations were extracted from the latest run.")
    lines.extend(["", "## Defaults"])
    if payload["next_run_defaults"]:
        lines.extend(f"- {item}" for item in payload["next_run_defaults"])
    else:
        lines.append("- No next-run defaults were recorded.")
    lines.extend(["", "## Public research references", "Top references captured for this skill are included in run reports."])
    lines.append("")
    return "\n".join(lines)


def write_self_improvement_artifacts(
    *,
    repo: str | None,
    results_path_value: str | None,
    state_path_value: str | None,
    self_improvement_path_value: str | None,
    memory_path_value: str | None,
) -> tuple[Path, Path]:
    self_improvement_path = resolve_path(
        repo, self_improvement_path_value, DEFAULT_SELF_IMPROVEMENT_PATH
    )
    atomic_write_text(
        self_improvement_path,
        build_self_improvement_report(
            repo=repo,
            results_path_value=results_path_value,
            state_path_value=state_path_value,
        ),
    )
    memory_path = resolve_path(repo, memory_path_value, DEFAULT_MEMORY_PATH)
    atomic_write_text(
        memory_path,
        build_memory_file(
            repo=repo,
            results_path_value=results_path_value,
            state_path_value=state_path_value,
        ),
    )
    return self_improvement_path, memory_path


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def serialize_dataclass(instance: Any) -> dict[str, Any]:
    return asdict(instance)
