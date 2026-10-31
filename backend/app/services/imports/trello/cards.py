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

"""Each Trello card as a draft card, in the order the import writes them.

Order is list by list (by ``pos``), then card ``pos``, then id, so it is
stable for one stored board and resume indexes always mean the same card.
Text is cut to our column and product limits here, once.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from app.models.board_card import CARD_TITLE_LENGTH
from app.models.board_card_detail import CHECKLIST_GROUP_LENGTH
from app.services.boards.constants import (
    CARD_DESCRIPTION_MAX_CHARS,
    CHECKLIST_MAX_ITEMS,
    CHECKLIST_TEXT_MAX_CHARS,
    COMMENT_MAX_CHARS,
)
from app.services.imports.trello.constants import TRELLO_CHECK_ITEM_DONE, UNTITLED_CARD
from app.services.imports.trello.parse import TrelloAction, TrelloCard, TrelloExport

_COVER_KEYS = ("idAttachment", "color", "idUploadedBackground")


@dataclass(frozen=True)
class ChecklistLine:
    """One checklist item, with the checklist it came from."""

    group: str | None
    text: str
    done: bool


@dataclass(frozen=True)
class CommentDraft:
    """A comment, with its original date and Trello author."""

    at: datetime | None
    member_id: str
    member_name: str
    text: str


@dataclass(frozen=True)
class AttachmentDraft:
    """A Trello attachment: a link, or (``is_upload``) a file Trello holds."""

    id: str
    name: str
    url: str
    is_upload: bool


@dataclass
class CardDraft:
    """Everything one card brings, before it's mapped onto a board."""

    id: str
    list_id: str
    title: str
    description: str | None
    closed: bool
    start_at: datetime | None
    due_at: datetime | None
    due_done: bool
    member_ids: list[str]
    label_ids: list[str]
    short_link: str
    url: str
    checklist: list[ChecklistLine] = field(default_factory=list)
    comments: list[CommentDraft] = field(default_factory=list)
    attachments: list[AttachmentDraft] = field(default_factory=list)
    # What this card carries that the import drops, by kind.
    dropped: dict[str, int] = field(default_factory=dict)


def card_drafts(export: TrelloExport) -> list[CardDraft]:
    """Every card on the board, in import order."""
    list_order = {
        lst.id: i for i, lst in enumerate(sorted(export.lists, key=lambda x: (x.pos, x.id)))
    }
    unknown = len(list_order)
    cards = sorted(export.cards, key=lambda c: (list_order.get(c.id_list, unknown), c.pos, c.id))
    names = {m.id: m.full_name for m in export.members}
    checklists = _checklists(export)
    comments = _comments(export, names)
    return [_draft(c, checklists.get(c.id, []), comments.get(c.id, [])) for c in cards]


def _draft(
    card: TrelloCard, checklist: list[ChecklistLine], comments: list[CommentDraft]
) -> CardDraft:
    dropped = {
        "custom_fields": len(card.custom_field_items),
        "power_up_data": len(card.plugin_data),
        "covers": int(any((card.cover or {}).get(key) for key in _COVER_KEYS)),
        "checklist_items": max(len(checklist) - CHECKLIST_MAX_ITEMS, 0),
    }
    return CardDraft(
        id=card.id,
        list_id=card.id_list,
        title=card.name.strip()[:CARD_TITLE_LENGTH].strip() or UNTITLED_CARD,
        description=card.desc[:CARD_DESCRIPTION_MAX_CHARS] or None,
        closed=card.closed,
        start_at=card.start,
        due_at=card.due,
        due_done=card.due_complete,
        member_ids=list(dict.fromkeys(card.id_members)),
        label_ids=list(dict.fromkeys(card.id_labels)),
        short_link=card.short_link,
        url=card.url,
        checklist=checklist[:CHECKLIST_MAX_ITEMS],
        comments=comments,
        attachments=[
            AttachmentDraft(id=a.id, name=a.name, url=a.url, is_upload=a.is_upload)
            for a in card.attachments
        ],
        dropped={kind: n for kind, n in dropped.items() if n},
    )


def _checklists(export: TrelloExport) -> dict[str, list[ChecklistLine]]:
    lines: dict[str, list[ChecklistLine]] = defaultdict(list)
    for checklist in sorted(export.checklists, key=lambda c: (c.pos, c.id)):
        group = checklist.name.strip()[:CHECKLIST_GROUP_LENGTH] or None
        for item in sorted(checklist.check_items, key=lambda i: (i.pos, i.id)):
            text = item.name.strip()[:CHECKLIST_TEXT_MAX_CHARS]
            if text:
                done = item.state == TRELLO_CHECK_ITEM_DONE
                lines[checklist.id_card].append(ChecklistLine(group=group, text=text, done=done))
    return lines


def _comments(export: TrelloExport, names: dict[str, str]) -> dict[str, list[CommentDraft]]:
    by_card: dict[str, list[TrelloAction]] = defaultdict(list)
    seen: set[str] = set()
    for action in export.comments():
        if action.id not in seen and action.card_id and action.data.text.strip():
            seen.add(action.id)
            by_card[action.card_id].append(action)
    drafts: dict[str, list[CommentDraft]] = {}
    for card_id, actions in by_card.items():
        # Trello lists newest first; a card's history reads oldest first.
        actions.sort(key=lambda a: (a.date is None, a.date or datetime.min, a.id))
        drafts[card_id] = [_comment(a, names) for a in actions]
    return drafts


def _comment(action: TrelloAction, names: dict[str, str]) -> CommentDraft:
    member_id = action.id_member_creator or (
        action.member_creator.id if action.member_creator else ""
    )
    name = names.get(member_id) or (
        action.member_creator.full_name if action.member_creator else ""
    )
    return CommentDraft(
        at=action.date,
        member_id=member_id,
        member_name=name,
        text=action.data.text[:COMMENT_MAX_CHARS],
    )
