"""Rule engine — pure function, no side effects.

Evaluates campaign state against the ladder of rules and returns
a recommended action. No HTTP requests, no DB writes.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class ActionType(str, Enum):
    SET_BUDGET = "set_budget"
    STOP = "stop"
    MANUAL_REVIEW = "manual_review"
    WAIT = "wait"


@dataclass
class Action:
    type: ActionType
    target_budget: float | None = None
    reason: str = ""


@dataclass
class CampaignState:
    spend: float
    leads: int
    current_budget: float
    last_budget_change_at: datetime | None = None
    link_clicks: int = 0


# Default stop thresholds: (min_spend, max_leads_to_stop)
DEFAULT_STOP_THRESHOLDS: list[tuple[float, int]] = [
    (7, 0),
    (15, 1),
    (23, 2),
    (31, 3),
    (39, 4),
]

# Default budget steps: (min_leads, target_budget) — checked top-down
DEFAULT_BUDGET_STEPS: list[tuple[int, float]] = [
    (6, 250),
    (4, 150),
    (2, 75),
]

CPC_STOP_SPEND = 2.5
CPC_STOP_MAX = 0.45
CPL_STOP_SPEND = 47.0
CPL_STOP_MAX = 10.0
MANUAL_REVIEW_LEADS = 7
COOLDOWN_HOURS = 1


def evaluate(
    state: CampaignState,
    now: datetime,
    stop_thresholds: list[tuple[float, int]] | None = None,
    budget_steps: list[tuple[int, float]] | None = None,
    cpc_stop_spend: float = CPC_STOP_SPEND,
    cpc_stop_max: float = CPC_STOP_MAX,
    cpl_stop_spend: float = CPL_STOP_SPEND,
    cpl_stop_max: float = CPL_STOP_MAX,
    manual_review_leads: int = MANUAL_REVIEW_LEADS,
    cooldown_hours: int = COOLDOWN_HOURS,
) -> Action:
    """Evaluate campaign state and return recommended action.

    Order of checks:
    1. STOP — always runs, even during cooldown
    2. Manual review — 7+ leads
    3. Cooldown — blocks budget changes only
    4. Budget increase — only up, never down
    """
    if stop_thresholds is None:
        stop_thresholds = DEFAULT_STOP_THRESHOLDS
    if budget_steps is None:
        budget_steps = DEFAULT_BUDGET_STEPS

    # 0. CPC early-stop (high CPC = bad traffic, kill fast)
    if state.link_clicks > 0 and state.spend >= cpc_stop_spend:
        cpc = state.spend / state.link_clicks
        if cpc > cpc_stop_max:
            return Action(
                type=ActionType.STOP,
                reason=f"CPC ${cpc:.2f} > ${cpc_stop_max} at spend ${state.spend:.2f} ({state.link_clicks} clicks)",
            )

    # 1. STOP checks (always, even during cooldown)
    for spend_limit, max_leads in stop_thresholds:
        if state.spend >= spend_limit and state.leads <= max_leads:
            return Action(
                type=ActionType.STOP,
                reason=f"spend ${state.spend:.0f} >= ${spend_limit} with {state.leads} leads (max {max_leads})",
            )

    # CPL stop
    if state.spend >= cpl_stop_spend and state.leads >= 5:
        cpl = state.spend / state.leads
        if cpl > cpl_stop_max:
            return Action(
                type=ActionType.STOP,
                reason=f"CPL ${cpl:.2f} > ${cpl_stop_max} at spend ${state.spend:.0f}",
            )

    # 2. Manual review for 7+ leads
    if state.leads >= manual_review_leads:
        return Action(
            type=ActionType.MANUAL_REVIEW,
            reason=f"{state.leads} leads — manual review needed",
        )

    # 3. Cooldown check (only blocks budget changes)
    if state.last_budget_change_at:
        cooldown_end = state.last_budget_change_at + timedelta(hours=cooldown_hours)
        if now < cooldown_end:
            return Action(
                type=ActionType.WAIT,
                reason=f"cooldown until {cooldown_end.isoformat()}",
            )

    # 4. Budget increases (only up, never down)
    for min_leads, target_budget in budget_steps:
        if state.leads >= min_leads and state.current_budget < target_budget:
            return Action(
                type=ActionType.SET_BUDGET,
                target_budget=target_budget,
                reason=f"{state.leads} leads >= {min_leads} — budget ${state.current_budget:.0f} → ${target_budget:.0f}",
            )

    return Action(type=ActionType.WAIT, reason="no action needed")
