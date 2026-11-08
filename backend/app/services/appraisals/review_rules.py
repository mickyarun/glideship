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

"""The scoring rules for self-reviews and manager reviews (pure).

Bands run 1 (always exceeds) to 5 (does not meet). A self-score of 1 or 2
needs at least two pieces of evidence. The manager agrees with one click
or changes a value with a reason the employee will read; moving to band
1 or 2 needs two pieces of evidence and to band 5 at least one. With no
self-score, the manager scores from scratch under the same rules and
says why. The final value is the employee's when the manager agrees,
the manager's when they change it. A self-score saved but never
submitted counts as no self-score at all.
"""

from dataclasses import dataclass

from app.models.appraisal import Appraisal
from app.models.appraisal_enums import GoalResult
from app.models.appraisal_goal import AppraisalGoal

HIGH_BANDS = frozenset({1, 2})


def submitted_band(appraisal: Appraisal) -> int | None:
    """The self-score's band, only once submitted: a draft is nobody else's business."""
    return appraisal.self_band if appraisal.self_submitted_at else None


def submitted_result(appraisal: Appraisal, goal: AppraisalGoal) -> GoalResult | None:
    """A goal's self-score, only once the self-review was submitted."""
    return goal.self_result if appraisal.self_submitted_at else None


LOW_BAND = 5
HIGH_EVIDENCE = 2


def self_problem(
    band: int | None, evidence: int, results: dict[str, GoalResult | None]
) -> str | None:
    """Why a self-review can't be submitted yet, or None."""
    if band is None:
        return "Pick an overall band."
    if band in HIGH_BANDS and evidence < HIGH_EVIDENCE:
        return "Bands 1 and 2 need at least two pieces of evidence."
    if any(result is None for result in results.values()):
        return "Score each goal: achieved, partly or not yet."
    return None


@dataclass(frozen=True)
class BandDecision:
    """The manager's call on the overall band."""

    agree: bool
    band: int | None
    reason: str
    evidence: int


def band_problem(self_band: int | None, decision: BandDecision) -> str | None:
    """Why the manager's band can't be submitted, or None."""
    if decision.agree:
        return None if self_band is not None else "There is no self-score to agree with."
    band = decision.band
    if band is None:
        return "Pick the band."
    if not decision.reason.strip():
        return "Say why; they'll read this."
    if band in HIGH_BANDS and decision.evidence < HIGH_EVIDENCE:
        return "Band 1 or 2 needs at least two pieces of evidence."
    if band == LOW_BAND and decision.evidence < 1:
        return "Band 5 needs evidence."
    return None


def final_band(self_band: int | None, decision: BandDecision) -> int | None:
    """The band that is shared."""
    return self_band if decision.agree else decision.band


@dataclass(frozen=True)
class GoalDecision:
    """The manager's call on one goal's result."""

    agree: bool
    result: GoalResult | None
    reason: str


def goal_problem(self_result: GoalResult | None, decision: GoalDecision) -> str | None:
    """Why the manager's result for a goal can't be submitted, or None."""
    if decision.agree:
        return None if self_result is not None else "There is no self-score to agree with."
    if decision.result is None:
        return "Pick the result for each goal."
    if not decision.reason.strip():
        return "Say why each result changed; they'll read this."
    return None


def final_result(self_result: GoalResult | None, decision: GoalDecision) -> GoalResult | None:
    """The goal result that is shared."""
    return self_result if decision.agree else decision.result
