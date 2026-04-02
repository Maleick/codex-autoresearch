from __future__ import annotations

import json

from scripts.autoresearch_subagent_plan import build_subagent_pool_plan, render_subagent_pool_plan


def test_subagent_pool_plan_is_stable_and_normalized():
    plan = build_subagent_pool_plan(
        goal="  Reduce auth failures  ",
        scope="  services/api  ",
        mode="  Fix  ",
    )
    rendered = render_subagent_pool_plan(
        goal="  Reduce auth failures  ",
        scope="  services/api  ",
        mode="  Fix  ",
    )

    assert plan["kind"] == "autoresearch_subagent_pool"
    assert plan["goal"] == "Reduce auth failures"
    assert plan["scope"] == "services/api"
    assert plan["mode"] == "fix"
    assert plan["role_limit"] == 6
    assert plan["standing_pool"] is True
    assert plan["reuse_across_iterations"] is True
    assert plan["orchestrator_role_id"] == "orchestrator"
    assert plan["state_owner"] == "orchestrator"
    assert plan["fallback_mode"] == "serial"
    assert plan["specialization"] == "security_reviewer"
    assert [role["id"] for role in plan["roles"]] == [
        "orchestrator",
        "scout",
        "analyst",
        "verifier",
        "synthesizer",
        "security_reviewer",
    ]
    assert json.loads(rendered) == plan
    assert rendered == render_subagent_pool_plan(
        goal="  Reduce auth failures  ",
        scope="  services/api  ",
        mode="  Fix  ",
    )


def test_subagent_pool_plan_caps_roles_at_six():
    plan = build_subagent_pool_plan(
        goal="Debug security release learn scenario regressions",
        scope="cli auth rollout docs",
        mode="ship",
    )

    assert len(plan["roles"]) == 6
    assert plan["orchestrator_role_id"] == "orchestrator"
    assert [role["id"] for role in plan["roles"]] == [
        "orchestrator",
        "scout",
        "analyst",
        "verifier",
        "synthesizer",
        "security_reviewer",
    ]
    assert plan["specialization"] == "security_reviewer"


def test_subagent_pool_plan_requires_goal_and_mode():
    for kwargs in (
        {"goal": "", "mode": "plan"},
        {"goal": "Investigate flaky tests", "mode": "   "},
    ):
        try:
            build_subagent_pool_plan(**kwargs)
        except RuntimeError:
            continue
        raise AssertionError("expected plan builder to reject missing required fields")
