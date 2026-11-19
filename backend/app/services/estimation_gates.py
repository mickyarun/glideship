# Copyright 2025-2026 Arun Rajkumar
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Turnaround model for review / sign-off gate phases.

Gate phases (``bud``, ``uat``, ``code_review`` — see ``phase_roles.PHASE_KIND``)
are not hands-on-keyboard work; they are *review latency*: how long until a
reviewer picks the BUD up and signs off. That latency is bounded and largely
independent of the effort-days an LLM might estimate, so running it through
``effort ÷ capacity`` over-stretches it — a PM at 0.21 capacity turned a 4-day
UAT estimate into ~20 wall-clock days.

Instead the estimator gives each gate a small **turnaround budget**:

    turnaround = base + penalty_per_backlog · reviewer_backlog   (capped at cap)

with the numbers per phase in ``GATE_PROFILES``.

``reviewer_backlog`` is how many BUDs sit ahead in that reviewer role's queue
(the primary role's active count), so a swamped reviewer is still slower — but
never a month. The orchestrator turns that single number into a PERT
triple via :func:`gate_pert` and feeds it to the Monte Carlo engine with a
capacity divisor of 1.0, so the engine stays a generic math kernel with no
knowledge of gate semantics.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import NamedTuple

import structlog

from app.models.user import UserRole
from app.services.capacity_provider import RoleLoad
from app.services.estimation_engine import PERTEstimate

logger = structlog.get_logger(__name__)


class GateProfile(NamedTuple):
    """Turnaround budget for one gate phase, in business days."""

    base: float  # an idle reviewer: pick it up and sign off
    penalty_per_backlog: float  # added per BUD queued on the reviewer role
    cap: float  # a sign-off is not continuous person-days, so it never exceeds this
    optimistic: float  # PERT spread around the turnaround, as multipliers
    pessimistic: float


# Spec sign-off keeps its original budget: the time a BUD spends in the
# spec stage is not measurable yet (its first entry has no status event).
SPEC_GATE = GateProfile(
    base=1.0, penalty_per_backlog=0.5, cap=4.0, optimistic=0.6, pessimistic=1.5
)

# Code review and UAT, measured on BUDs that started development from Aug to
# Nov 2026: code review took 1.3 / 3.0 / 5.9 business days at p50 / p70 /
# p85 and UAT 1.8 / 3.3 / 5.1, while the old budget (the spec one above)
# hit its 4-day cap almost every time. The reviewer role's whole active
# count is a weak queue signal, so the penalty is small and the cap low; the
# long pessimistic tail keeps the slow reviews in the variance and buffer.
# Sampled, a loaded reviewer gives 2.0 / 2.5 / 3.1 days, slightly ahead of
# what was measured.
REVIEW_GATE = GateProfile(
    base=1.0, penalty_per_backlog=0.1, cap=1.5, optimistic=0.5, pessimistic=4.0
)

GATE_PROFILES: dict[str, GateProfile] = {
    "bud": SPEC_GATE,
    "code_review": REVIEW_GATE,
    "uat": REVIEW_GATE,
}


def gate_profile(phase: str) -> GateProfile:
    """Return the turnaround budget for a gate phase (the spec budget if unlisted)."""
    return GATE_PROFILES.get(phase, SPEC_GATE)


def gate_turnaround_days(
    role_loads: dict[UserRole, RoleLoad],
    phase: str,
    chains: Mapping[str, tuple[UserRole, ...]],
) -> float:
    """Capped review-turnaround for one gate phase, in business days.

    ``reviewer_backlog`` is the primary owning role's active in-flight count
    (BUDs ahead in that reviewer's queue). An unknown phase or one whose role
    chain is empty falls back to the base turnaround — never raises, never
    inflates.
    """
    chain = chains.get(phase)
    if not chain:
        # A phase only reaches here if ``is_gate_phase`` returned True, i.e.
        # it is listed in ``PHASE_KIND`` as a gate — yet it has no owning
        # role chain. That means the two maps have drifted. Mirror the warn
        # that ``capacity_provider.phase_capacity`` emits for its empty-pool
        # case so the misconfiguration is observable, not a silent 1-day floor.
        logger.warning(
            "gate_phase_missing_role_chain",
            phase=phase,
            action=(
                "defaulting to base turnaround; PHASE_KIND lists this as a gate "
                "but the role chains have no owning role — the maps have drifted"
            ),
        )
        return gate_profile(phase).base
    profile = gate_profile(phase)
    reviewer_backlog = role_loads.get(chain[0], RoleLoad(0, 0)).active
    turnaround = profile.base + profile.penalty_per_backlog * reviewer_backlog
    return min(profile.cap, turnaround)


def gate_pert(turnaround_days: float, phase: str) -> PERTEstimate:
    """Build a PERT triple with the turnaround as the most likely value."""
    profile = gate_profile(phase)
    return PERTEstimate(
        optimistic=round(turnaround_days * profile.optimistic, 2),
        most_likely=round(turnaround_days, 2),
        pessimistic=round(turnaround_days * profile.pessimistic, 2),
    )
