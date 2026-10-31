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

"""What the Garden hears about a card run, on ``agent_activity:<org_id>`` like BUD agents.

The tag is plain values taken while the run's rows are loaded, so a run
that ends after its session was rolled back (a cancel, a crash) can still
tell the Garden, and the character it started stops. The card is named
only when its board is visible to the whole org.
"""

import uuid
from dataclasses import dataclass

from app.models.board_enums import BoardVisibility
from app.services.boards.agents.refs import RunRefs
from app.services.boards.reads import card_key
from app.services.event_bus import publish

_STATUS = {
    "skill_invoked": "in_progress",
    "skill_completed": "completed",
    "skill_failed": "failed",
}


@dataclass(frozen=True)
class GardenTag:
    """Everything a Garden event names, copied off the loaded rows."""

    org_id: uuid.UUID
    run_id: uuid.UUID
    skill_slug: str
    card_key: str | None

    @classmethod
    def of(cls, refs: RunRefs) -> "GardenTag":
        """The tag for a loaded run."""
        open_board = refs.board.visibility is BoardVisibility.ORG
        return cls(
            org_id=refs.card.org_id,
            run_id=refs.run.id,
            skill_slug=refs.skill.skill_slug,
            card_key=card_key(refs.board.key, refs.card.number) if open_board else None,
        )


def garden_event(tag: GardenTag, event_type: str) -> None:
    """Tell the Garden a board agent started (``skill_invoked``), finished or failed."""
    publish(
        f"agent_activity:{tag.org_id}",
        {
            "event_type": event_type,
            "status": _STATUS[event_type],
            "message": f"Skill '{tag.skill_slug}' on a board card",
            "skill_slug": tag.skill_slug,
            "actor_name": tag.skill_slug,
            "task_id": str(tag.run_id),
            "repo_name": None,
            "bud_number": None,
            "bud_title": None,
            "card_key": tag.card_key,
            "impacted_repo_names": [],
            "created_at": "",
        },
    )


class GardenRun:
    """One run's Garden events: the end is sent once, and only after the start."""

    def __init__(self) -> None:
        self.tag: GardenTag | None = None
        self._open = False

    def started(self) -> None:
        """The run started (``skill_invoked``)."""
        if self.tag is not None:
            self._open = True
            garden_event(self.tag, "skill_invoked")

    def ended(self, event_type: str) -> None:
        """The run completed or failed, if the Garden heard it start."""
        if self.tag is not None and self._open:
            self._open = False
            garden_event(self.tag, event_type)
