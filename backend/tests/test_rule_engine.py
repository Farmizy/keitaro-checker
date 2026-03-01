import pytest
from datetime import datetime, timedelta

from app.services.rule_engine import (
    evaluate,
    CampaignState,
    Action,
    ActionType,
)

NOW = datetime(2026, 3, 1, 12, 0, 0)


def _state(spend=0.0, leads=0, budget=30.0, last_change=None):
    return CampaignState(
        spend=spend,
        leads=leads,
        current_budget=budget,
        last_budget_change_at=last_change,
    )


# ── STOP rules ──────────────────────────────────────────────


class TestStopRules:
    def test_8_spend_0_leads(self):
        result = evaluate(_state(spend=8, leads=0), NOW)
        assert result.type == ActionType.STOP

    def test_16_spend_1_lead(self):
        result = evaluate(_state(spend=16, leads=1), NOW)
        assert result.type == ActionType.STOP

    def test_24_spend_2_leads(self):
        result = evaluate(_state(spend=24, leads=2), NOW)
        assert result.type == ActionType.STOP

    def test_32_spend_3_leads(self):
        result = evaluate(_state(spend=32, leads=3), NOW)
        assert result.type == ActionType.STOP

    def test_40_spend_4_leads(self):
        result = evaluate(_state(spend=40, leads=4), NOW)
        assert result.type == ActionType.STOP

    def test_cpl_above_10(self):
        # spend=60, leads=5 → CPL=12 > 10
        result = evaluate(_state(spend=60, leads=5), NOW)
        assert result.type == ActionType.STOP
        assert "CPL" in result.reason

    def test_cpl_exactly_10_no_stop(self):
        # spend=50, leads=5 → CPL=10, NOT > 10
        result = evaluate(_state(spend=50, leads=5), NOW)
        assert result.type != ActionType.STOP

    def test_cpl_below_10_no_stop(self):
        # spend=48, leads=6 → CPL=8 < 10
        result = evaluate(_state(spend=48, leads=6), NOW)
        assert result.type != ActionType.STOP

    def test_stop_works_during_cooldown(self):
        last_change = NOW - timedelta(minutes=30)
        result = evaluate(_state(spend=8, leads=0, last_change=last_change), NOW)
        assert result.type == ActionType.STOP

    def test_no_stop_below_threshold(self):
        result = evaluate(_state(spend=7.99, leads=0), NOW)
        assert result.type != ActionType.STOP

    def test_higher_threshold_applies(self):
        # spend=$32 with 2 leads: (24,2) triggers because 32>=24 and 2<=2
        result = evaluate(_state(spend=32, leads=2), NOW)
        assert result.type == ActionType.STOP


# ── Manual review ────────────────────────────────────────────


class TestManualReview:
    def test_7_leads(self):
        result = evaluate(_state(spend=48, leads=7), NOW)
        assert result.type == ActionType.MANUAL_REVIEW

    def test_10_leads(self):
        result = evaluate(_state(spend=50, leads=10), NOW)
        assert result.type == ActionType.MANUAL_REVIEW

    def test_7_leads_even_with_low_spend(self):
        result = evaluate(_state(spend=5, leads=7), NOW)
        assert result.type == ActionType.MANUAL_REVIEW


# ── Budget increase ──────────────────────────────────────────


class TestBudgetIncrease:
    def test_2_leads_budget_to_75(self):
        result = evaluate(_state(spend=16, leads=2, budget=30), NOW)
        assert result.type == ActionType.SET_BUDGET
        assert result.target_budget == 75

    def test_4_leads_budget_to_150(self):
        result = evaluate(_state(spend=32, leads=4, budget=75), NOW)
        assert result.type == ActionType.SET_BUDGET
        assert result.target_budget == 150

    def test_6_leads_budget_to_250(self):
        result = evaluate(_state(spend=48, leads=6, budget=150), NOW)
        assert result.type == ActionType.SET_BUDGET
        assert result.target_budget == 250

    def test_never_lower_budget(self):
        # 2 leads → target $75, but budget already $100 → skip
        result = evaluate(_state(spend=16, leads=2, budget=100), NOW)
        assert result.type == ActionType.WAIT

    def test_manual_budget_higher_than_all_steps(self):
        # Budget manually set to $300, leads=6 → target $250 < $300 → skip
        result = evaluate(_state(spend=48, leads=6, budget=300), NOW)
        assert result.type != ActionType.SET_BUDGET

    def test_budget_already_at_target(self):
        # budget == target → current_budget < target is False → skip
        result = evaluate(_state(spend=16, leads=2, budget=75), NOW)
        assert result.type == ActionType.WAIT

    def test_skips_to_higher_step(self):
        # 4 leads with budget=30 → should go to $150 (not $75)
        result = evaluate(_state(spend=32, leads=4, budget=30), NOW)
        assert result.type == ActionType.SET_BUDGET
        assert result.target_budget == 150

    def test_2_leads_no_spend_requirement(self):
        # Budget increase is by leads only, no spend check
        result = evaluate(_state(spend=0.5, leads=2, budget=30), NOW)
        assert result.type == ActionType.SET_BUDGET
        assert result.target_budget == 75


# ── Cooldown ─────────────────────────────────────────────────


class TestCooldown:
    def test_blocks_budget_increase(self):
        last_change = NOW - timedelta(minutes=30)
        result = evaluate(_state(spend=16, leads=2, budget=30, last_change=last_change), NOW)
        assert result.type == ActionType.WAIT
        assert "cooldown" in result.reason

    def test_expired_allows_budget(self):
        last_change = NOW - timedelta(hours=2)
        result = evaluate(_state(spend=16, leads=2, budget=30, last_change=last_change), NOW)
        assert result.type == ActionType.SET_BUDGET
        assert result.target_budget == 75

    def test_exactly_1_hour_allows(self):
        last_change = NOW - timedelta(hours=1)
        result = evaluate(_state(spend=16, leads=2, budget=30, last_change=last_change), NOW)
        assert result.type == ActionType.SET_BUDGET

    def test_does_not_block_stop(self):
        last_change = NOW - timedelta(minutes=30)
        result = evaluate(_state(spend=8, leads=0, last_change=last_change), NOW)
        assert result.type == ActionType.STOP

    def test_does_not_block_manual_review(self):
        last_change = NOW - timedelta(minutes=30)
        result = evaluate(_state(spend=5, leads=7, last_change=last_change), NOW)
        assert result.type == ActionType.MANUAL_REVIEW


# ── Wait (no action) ────────────────────────────────────────


class TestWait:
    def test_low_spend_low_leads(self):
        result = evaluate(_state(spend=3, leads=0), NOW)
        assert result.type == ActionType.WAIT

    def test_1_lead_under_16_spend(self):
        result = evaluate(_state(spend=10, leads=1), NOW)
        assert result.type == ActionType.WAIT

    def test_zero_everything(self):
        result = evaluate(_state(spend=0, leads=0, budget=30), NOW)
        assert result.type == ActionType.WAIT


# ── Edge cases ───────────────────────────────────────────────


class TestEdgeCases:
    def test_exact_spend_threshold(self):
        result = evaluate(_state(spend=8.0, leads=0), NOW)
        assert result.type == ActionType.STOP

    def test_just_below_stop_spend(self):
        result = evaluate(_state(spend=15.99, leads=1), NOW)
        assert result.type != ActionType.STOP

    def test_stop_priority_over_budget(self):
        # spend=$24, leads=2 → STOP (even though 2 leads could trigger budget)
        result = evaluate(_state(spend=24, leads=2, budget=30), NOW)
        assert result.type == ActionType.STOP

    def test_action_has_reason(self):
        result = evaluate(_state(spend=8, leads=0), NOW)
        assert result.reason != ""

    def test_custom_thresholds(self):
        custom_stops = [(5, 0)]
        custom_budgets = [(1, 50)]
        result = evaluate(
            _state(spend=5, leads=0),
            NOW,
            stop_thresholds=custom_stops,
            budget_steps=custom_budgets,
        )
        assert result.type == ActionType.STOP

    def test_custom_budget_steps(self):
        result = evaluate(
            _state(spend=0, leads=1, budget=20),
            NOW,
            budget_steps=[(1, 50)],
        )
        assert result.type == ActionType.SET_BUDGET
        assert result.target_budget == 50
