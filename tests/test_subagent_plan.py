from __future__ import annotations

import json

from scripts.autoresearch_subagent_plan import build_subagent_pool_plan, render_subagent_pool_plan


def test_subagent_plan_defaults_to_lite_pool_for_short_foreground_work():
    plan = build_subagent_pool_plan(goal="Clean docs", mode="foreground")

    assert plan["standing_pool"] is True
    assert plan["reuse_across_iterations"] is True
    assert plan["orchestrator_role_id"] == "orchestrator"
    assert plan["state_owner"] == "orchestrator"
    assert plan["fallback_mode"] == "serial"
    assert plan["execution_profile"] == "standard"
    assert plan["resource_tier"] == "lite"
    assert plan["activation"]["during_setup"] is False
    assert plan["recommended_active_role_ids"] == ["orchestrator", "scout", "verifier"]
    assert plan["fallback_policy"]["mode"] == "deterministic_role_order"
    assert plan["iteration_assignments"]["protocol"] == "orchestrator"
    assert len(plan["roles"]) == 5
    verifier = next(role for role in plan["roles"] if role["id"] == "verifier")
    assert verifier["active_by_default"] is True
    assert "Do not mutate autoresearch state." in verifier["handoff_prompt"]


def test_subagent_plan_uses_full_pool_and_specialization_for_fix_like_work():
    plan = build_subagent_pool_plan(
        goal="Reduce crash regressions",
        scope="services/api",
        mode="fix",
    )

    assert plan["resource_tier"] == "full"
    assert plan["specialization"] == "debugger"
    assert plan["activation"]["during_setup"] is True
    assert "standing pool" in plan["activation"]["reason"]
    assert plan["recommended_active_role_ids"] == [
        "orchestrator",
        "scout",
        "analyst",
        "verifier",
        "synthesizer",
        "debugger",
    ]
    assert len(plan["roles"]) == 6
    assert any(role["id"] == "debugger" for role in plan["roles"])
    assert plan["fallback_policy"]["mode"] == "deterministic_role_order"
    assert any(item["intent"] == "evidence" for item in plan["role_intent_routing"])
    assert plan["deduplication"]["require_unique_evidence_for_repeat_discards"] is True
    assert plan["reanchor_checklist"]
    assert plan["handoff_contract"]


def test_render_subagent_plan_is_stable_json():
    rendered_once = render_subagent_pool_plan(
        goal="Reduce flaky tests",
        scope="api/tests",
        mode="background",
    )
    rendered_twice = render_subagent_pool_plan(
        goal="Reduce flaky tests",
        scope="api/tests",
        mode="background",
    )

    assert rendered_once == rendered_twice
    payload = json.loads(rendered_once)
    assert payload["resource_tier"] == "full"
    assert payload["activation"]["during_resume"] is True


def test_subagent_plan_max_parallel_mode_exposes_intent_routing_and_dedupe_policy():
    plan = build_subagent_pool_plan(
        goal="Run ten hardening iterations with parallel agents",
        scope="skill runtime",
        mode="parallel",
    )

    assert plan["execution_profile"] == "max_parallelism"
    intents = {item["intent"] for item in plan["role_intent_routing"]}
    assert {"protocol", "implementation", "validation", "evidence"}.issubset(intents)
    assert plan["deduplication"]["require_unique_evidence_for_repeat_discards"] is True
    assert plan["deduplication"]["duplicate_window"] == 2
    assert plan["fallback_policy"]["mode"] == "deterministic_role_order"
    assert plan["fallback_policy"]["ordered_role_ids"][: len(plan["roles"])] == [
        role["id"] for role in plan["roles"]
    ]
    assert plan["iteration_assignments"]["coordinator"] == "orchestrator"
