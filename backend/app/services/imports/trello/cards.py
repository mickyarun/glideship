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
stable for one stored board and every run walks the same cards in the same
order; a position that isn't a number sorts last. A card in an archived
list counts as archived, so it follows the reviewer's archived-cards
choice exactly like a closed card. Text is cut to our column and product
limits here, once; a comment cut at the length cap counts as dropped.
"""

from collections import defaultdict
from datetime import datetime

from app.models.board_card import CARD_TITLE_LENGTH
from app.models.board_card_detail import CHECKLIST_GROUP_LENGTH
from app.services.boards.constants import (
    CARD_DESCRIPTION_MAX_CHARS,
    CHECKLIST_MAX_ITEMS,
    CHECKLIST_TEXT_MAX_CHARS,
    COMMENT_MAX_CHARS,
)
from app.services.imports.draft import (
    AttachmentDraft,
    CardDraft,
    ChecklistLine,
    CommentDraft,
    LabelDraft,
    SourceBoard,
)
from app.services.imports.text import http_url, truncated
from app.services.imports.trello.constants import (
    TRELLO_CHECK_ITEM_DONE,
    TRELLO_SHORT_LINK_PATTERN,
    UNTITLED_CARD,
)
from app.services.imports.trello.mapper import author_label, label_name, nearest_label_color
from app.services.imports.trello.models import TrelloAction, TrelloCard, TrelloExport


def source_board(export: TrelloExport) -> SourceBoard:
    """The board's cards in import order, and its labels."""
    labels = [
        LabelDraft(id=lb.id, name=label_name(lb), color=nearest_label_color(lb.color))
        for lb in export.labels
    ]
    return SourceBoard(cards=card_drafts(export), labels=labels)


def card_drafts(export: TrelloExport) -> list[CardDraft]:
    """Every card on the board, in import order."""
    lists = sorted(export.lists, key=lambda x: (x.pos, x.id))
    order = {lst.id: i for i, lst in enumerate(lists)}
    archived_lists = {lst.id for lst in lists if lst.closed}
    unknown = len(order)
    cards = sorted(export.cards, key=lambda c: (order.get(c.id_list, unknown), c.pos, c.id))
    names = {m.id: m.full_name for m in export.members}
    checklists = _checklists(export)
    comments = _comments(export, names)
    return [
        _draft(
            c,
            checklists.get(c.id, []),
            comments.get(c.id, []),
            in_archived_list=c.id_list in archived_lists,
        )
        for c in cards
    ]


def _draft(
    card: TrelloCard,
    checklist: list[ChecklistLine],
    comments: list[tuple[CommentDraft, bool]],
    *,
    in_archived_list: bool,
) -> CardDraft:
    dropped = {
        "custom_fields": card.custom_field_items,
        "power_up_data": card.plugin_data,
        "covers": int(card.cover),
        "checklist_items": max(len(checklist) - CHECKLIST_MAX_ITEMS, 0),
        "comments_truncated": sum(cut for _, cut in comments),
    }
    short_link = card.short_link if TRELLO_SHORT_LINK_PATTERN.fullmatch(card.short_link) else ""
    return CardDraft(
        id=card.id,
        group_id=card.id_list,
        title=card.name.strip()[:CARD_TITLE_LENGTH].strip() or UNTITLED_CARD,
        description=card.desc[:CARD_DESCRIPTION_MAX_CHARS] or None,
        closed=card.closed or in_archived_list,
        start_at=card.start,
        due_at=card.due,
        due_done=card.due_complete,
        member_ids=list(dict.fromkeys(card.id_members)),
        label_ids=list(dict.fromkeys(card.id_labels)),
        source_key=short_link,
        url=http_url(card.url),
        checklist=checklist[:CHECKLIST_MAX_ITEMS],
        comments=[comment for comment, _ in comments],
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


def _comments(
    export: TrelloExport, names: dict[str, str]
) -> dict[str, list[tuple[CommentDraft, bool]]]:
    """Card id → its comments, oldest first, each with whether it was cut."""
    by_card: dict[str, list[TrelloAction]] = defaultdict(list)
    seen: set[str] = set()
    for action in export.comments():
        if action.id not in seen and action.card_id and action.data.text.strip():
            seen.add(action.id)
            by_card[action.card_id].append(action)
    drafts: dict[str, list[tuple[CommentDraft, bool]]] = {}
    for card_id, actions in by_card.items():
        # Trello lists newest first; a card's history reads oldest first.
        actions.sort(key=lambda a: (a.date is None, a.date or datetime.min, a.id))
        drafts[card_id] = [_comment(a, names) for a in actions]
    return drafts


def _comment(action: TrelloAction, names: dict[str, str]) -> tuple[CommentDraft, bool]:
    creator = action.member_creator
    member_id = action.id_member_creator or (creator.id if creator else "")
    name = names.get(member_id) or (creator.full_name if creator else "")
    text, cut = truncated(action.data.text, COMMENT_MAX_CHARS)
    draft = CommentDraft(
        at=action.date, member_id=member_id, author_label=author_label(name), text=text
    )
    return draft, cut
