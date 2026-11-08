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

"""Writing and reading a goal's append-only history."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import GoalRevisionKind
from app.models.appraisal_goal import AppraisalGoal
from app.models.appraisal_goal_revision import AppraisalGoalRevision
from app.services.appraisals import crypto


@dataclass(frozen=True)
class GoalText:
    """A goal's words: what it is and how you'll know."""

    title: str
    measure: str

    @classmethod
    def of(cls, goal: AppraisalGoal) -> "GoalText":
        """The goal's words as they are now."""
        return cls(crypto.unseal(goal, "title") or "", crypto.unseal(goal, "measure") or "")

    def as_json(self) -> dict[str, str]:
        """For the encrypted before/after blobs."""
        return {"title": self.title, "measure": self.measure}


def record(
    db: AsyncSession,
    goal: AppraisalGoal,
    actor_id: uuid.UUID,
    kind: GoalRevisionKind,
    *,
    before: GoalText | None = None,
    after: GoalText | None = None,
    reason: str | None = None,
) -> None:
    """Stage one history entry in the caller's transaction."""
    revision = AppraisalGoalRevision(
        id=uuid.uuid4(), org_id=goal.org_id, goal_id=goal.id, changed_by=actor_id, kind=kind
    )
    crypto.seal_json(revision, "before", before.as_json() if before else None)
    crypto.seal_json(revision, "after", after.as_json() if after else None)
    crypto.seal(revision, "reason", reason)
    db.add(revision)


@dataclass(frozen=True)
class HistoryEntry:
    """One decrypted history line."""

    kind: GoalRevisionKind
    changed_by: uuid.UUID
    at: datetime
    before: GoalText | None
    after: GoalText | None
    reason: str | None


def read(revision: AppraisalGoalRevision) -> HistoryEntry:
    """Decrypt one revision."""
    before = crypto.unseal_json(revision, "before")
    after = crypto.unseal_json(revision, "after")
    return HistoryEntry(
        kind=revision.kind,
        changed_by=revision.changed_by,
        at=revision.created_at,
        before=GoalText(**before) if before else None,
        after=GoalText(**after) if after else None,
        reason=crypto.unseal(revision, "reason"),
    )
