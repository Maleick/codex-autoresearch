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
    assert plan["resource_tier"] == "lite"
    assert plan["activation"]["during_setup"] is False
    assert plan["recommended_active_role_ids"] == ["orchestrator", "scout", "verifier"]
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
