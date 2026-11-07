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

"""Every status and option of the appraisal tables, each a Postgres enum."""

from enum import StrEnum

from sqlalchemy import Enum


def pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """A Postgres enum column type that stores the members' values."""
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class ReviewPeriod(StrEnum):
    """How often goals are scored and reviewed."""

    QUARTERLY = "quarterly"
    HALF_YEARLY = "half_yearly"
    YEARLY = "yearly"


class CheckInCadence(StrEnum):
    """How often employees check in."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class FeedbackCadence(StrEnum):
    """How often managers give feedback between reviews."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    # Quarterly reviews only: the review itself is the manager's feedback.
    IN_REVIEW = "in_review"


class CycleStatus(StrEnum):
    """Where a cycle is."""

    DRAFT = "draft"
    ACTIVE = "active"
    REVIEWING = "reviewing"
    CLOSED = "closed"


class DraftStatus(StrEnum):
    """State of an AI draft on a check-in or appraisal."""

    # No draft wanted (manual mode) or a permanent error.
    NONE = "none"
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class CheckInStatus(StrEnum):
    """Where a check-in is."""

    OPEN = "open"
    EMPLOYEE_ADDED = "employee_added"
    MISSED = "missed"


class DraftingMode(StrEnum):
    """Whether an appraisal gets AI drafts, fixed when the cycle opens."""

    AI = "ai"
    MANUAL = "manual"


class AppraisalStatus(StrEnum):
    """Where one person's appraisal is."""

    ENROLLED = "enrolled"
    SELF_REVIEW = "self_review"
    MANAGER_REVIEW = "manager_review"
    CALIBRATION = "calibration"
    SHARED = "shared"
    ACKNOWLEDGED = "acknowledged"
    WITHDRAWN = "withdrawn"


class GoalResult(StrEnum):
    """How a goal went."""

    ACHIEVED = "achieved"
    PARTLY = "partly"
    NOT_YET = "not_yet"


class GoalOrigin(StrEnum):
    """Who or what first wrote a goal."""

    EMPLOYEE_OWN = "employee_own"
    MANAGER_ADDED = "manager_added"
    AI_SUGGESTED = "ai_suggested"
    ROLE_LIBRARY = "role_library"


class GoalStatus(StrEnum):
    """Where a goal is. Only accepted goals count."""

    SUGGESTED = "suggested"
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"


class SuggestionBasis(StrEnum):
    """What a suggested goal was drawn from, shown as its badge."""

    FEEDBACK = "feedback"
    LAST_PERIOD = "last_period"
    BLOCKER = "blocker"
    TREND = "trend"
    ROLE_LIBRARY = "role_library"


class FeedbackStatus(StrEnum):
    """Where one manager feedback item is."""

    OPEN = "open"
    DONE = "done"


class GoalRevisionKind(StrEnum):
    """One entry in a goal's history."""

    CREATED = "created"
    EDITED = "edited"
    CONFIRMED = "confirmed"
    REWORD_ASKED = "reword_asked"
    DECLINED = "declined"
    REMOVED = "removed"


class EvidenceHeading(StrEnum):
    """The four headings a check-in groups work under."""

    DELIVERY_QUALITY = "delivery_quality"
    INITIATIVE = "initiative"
    TEAM = "team"
    GROWTH = "growth"


class FactSource(StrEnum):
    """Where a fact comes from; role templates switch sources on and off."""

    BUDS = "buds"
    PULL_REQUESTS = "pull_requests"
    CODE_REVIEWS = "code_reviews"
    BUGS = "bugs"
    BOARD_CARDS = "board_cards"
    LEARNINGS = "learnings"
    ESTIMATES = "estimates"
    SKILLS = "skills"
    QA_EVIDENCE = "qa_evidence"
    HR_RECORDS = "hr_records"


class DraftKind(StrEnum):
    """What an AI run wrote."""

    CHECK_IN = "check_in"
    PERIOD_SUMMARY = "period_summary"


class TrendsStatus(StrEnum):
    """Whether a role template's market trends may feed suggestions."""

    DRAFT = "draft"
    APPROVED = "approved"


class GoalCheck(StrEnum):
    """A manager's view of a goal mid-period, in quarterly feedback.

    Kept in JSONB, so it has no Postgres type; it never decides the result.
    """

    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    OFF_TRACK = "off_track"
