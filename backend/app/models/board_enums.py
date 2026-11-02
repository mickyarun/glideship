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

"""Postgres enums for boards, their stages, cards and card documents."""

from enum import StrEnum

from sqlalchemy import Enum


def pg_enum(enum_cls: type[StrEnum], name: str, *, create_type: bool = True) -> Enum:
    """A Postgres enum column type that stores each member's ``.value``."""
    return Enum(
        enum_cls,
        name=name,
        create_type=create_type,
        values_callable=lambda e: [x.value for x in e],
    )


class BoardStatus(StrEnum):
    """Whether a board is in use or archived."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class BoardVisibility(StrEnum):
    """Who can find a board: the whole org, or only its members and teams."""

    ORG = "org"
    MEMBERS = "members"


class BoardMemberRole(StrEnum):
    """A person's role on one board, lowest first.

    Declaration order is the rank: Postgres orders enum values as declared,
    so ``max(role)`` in SQL and :meth:`at_least` here agree.
    """

    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"

    def at_least(self, minimum: "BoardMemberRole") -> bool:
        """True when this role ranks at or above ``minimum``."""
        order = list(BoardMemberRole)
        return order.index(self) >= order.index(minimum)


class BoardStageCategory(StrEnum):
    """What a user-named stage means for metrics and handover."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELED = "canceled"


# Categories a card is finished in; moving out of them reopens it.
COMPLETED_CATEGORIES = frozenset({BoardStageCategory.DONE, BoardStageCategory.CANCELED})


class BoardLabelColor(StrEnum):
    """Label colours, rendered through the ``label-*`` theme colours."""

    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"
    PURPLE = "purple"
    BLUE = "blue"
    SKY = "sky"
    LIME = "lime"
    PINK = "pink"
    BLACK = "black"


class BoardCardEventType(StrEnum):
    """Kinds of entry in a card's activity history."""

    CREATED = "created"
    MOVED = "moved"
    MOVED_BOARD = "moved_board"
    EDITED = "edited"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    COMMENTED = "commented"
    ARCHIVED = "archived"
    RESTORED = "restored"
    HANDED_OVER = "handed_over"
    RETURNED = "returned"
    DELIVERED = "delivered"
    # Every live handover on the card has reached prod.
    FULLY_DELIVERED = "fully_delivered"
    IMPORTED = "imported"
    DOC_UPDATED = "doc_updated"
    AI_RUN = "ai_run"
    # A pull request or commit on a linked repository named the card's key.
    REPO_ACTIVITY = "repo_activity"


class BoardHandoverStatus(StrEnum):
    """Whether a card's handover to a BUD stands, or the BUD was sent back."""

    ACTIVE = "active"
    RETURNED = "returned"


class BoardAttachmentKind(StrEnum):
    """A stored file, or a link to somewhere else."""

    FILE = "file"
    LINK = "link"


class BoardCardDocKind(StrEnum):
    """Documents a card can carry next to its description."""

    PRD = "prd"
    DESIGN_BRIEF = "design_brief"
    NOTES = "notes"


class BoardCardDocState(StrEnum):
    """Where one version of a card document stands."""

    CURRENT = "current"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class StageRequiredField(StrEnum):
    """What a card must have before it may enter a stage that lists it."""

    ASSIGNEE = "assignee"
    DUE_DATE = "due_date"
    PRIORITY = "priority"
    LABEL = "label"
    DESCRIPTION = "description"
    PRD = "prd"


class BoardAccessVia(StrEnum):
    """How someone holds their role on a board (computed, never stored).

    ``member`` is their own row, ``team`` a team's row, ``permission`` the
    ``boards:manage`` permission, and ``org`` the board's org-wide visibility.
    """

    MEMBER = "member"
    TEAM = "team"
    PERMISSION = "permission"
    ORG = "org"
