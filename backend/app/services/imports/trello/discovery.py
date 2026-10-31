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

"""The review screen's summary of a parsed board, with our suggestions filled in."""

import uuid
from collections import Counter
from collections.abc import Iterable

from app.models.external_import import ImportMode
from app.schemas.boards.trello_discovery import (
    DiscoveredLabel,
    DiscoveredList,
    DiscoveredMember,
    DiscoveryCounts,
    DroppedCounts,
    TrelloDiscovery,
    TrelloWarning,
)
from app.services.imports.draft import CardDraft
from app.services.imports.text import http_url
from app.services.imports.trello.mapper import (
    nearest_label_color,
    stage_name,
    suggest_category,
    suggest_users,
)
from app.services.imports.trello.models import TrelloExport


def build_discovery(
    export: TrelloExport,
    drafts: list[CardDraft],
    people: Iterable[tuple[uuid.UUID, str]],
    mode: ImportMode,
) -> TrelloDiscovery:
    """Lists, labels and members with suggestions; counts; what gets dropped; warnings.

    The action cap only applies to uploaded exports: API mode pages every comment.
    """
    per_list = Counter(d.group_id for d in drafts)
    lists = sorted(export.lists, key=lambda x: (x.pos, x.id))
    open_ids = [lst.id for lst in lists if not lst.closed]
    last_open = open_ids[-1] if open_ids else None
    dropped: Counter[str] = Counter()
    for draft in drafts:
        dropped.update(draft.dropped)
    suggested = suggest_users({m.id: m.full_name for m in export.members}, people)
    warnings = (
        [TrelloWarning.ACTION_CAP] if mode is ImportMode.UPLOAD and export.action_cap_hit else []
    )
    return TrelloDiscovery(
        board_id=export.id,
        board_name=export.name,
        board_url=http_url(export.url),
        lists=[
            DiscoveredList(
                id=lst.id,
                name=lst.name,
                closed=lst.closed,
                card_count=per_list[lst.id],
                suggested_name=stage_name(lst.name),
                suggested_category=suggest_category(lst.name, is_last=lst.id == last_open),
                suggested_skip=lst.closed,
            )
            for lst in lists
        ],
        labels=[
            DiscoveredLabel(
                id=label.id,
                name=label.name,
                color=label.color,
                mapped_color=nearest_label_color(label.color),
            )
            for label in export.labels
        ],
        members=[
            DiscoveredMember(
                id=m.id,
                full_name=m.full_name,
                username=m.username,
                suggested_user_id=suggested.get(m.id),
            )
            for m in export.members
        ],
        counts=DiscoveryCounts(
            cards=len(drafts),
            archived_cards=sum(d.closed for d in drafts),
            comments=sum(len(d.comments) for d in drafts),
            checklist_items=sum(len(d.checklist) for d in drafts),
            attachments=sum(len(d.attachments) for d in drafts),
            actions=export.action_count,
        ),
        dropped=DroppedCounts(
            custom_fields=dropped["custom_fields"],
            power_up_data=dropped["power_up_data"],
            covers=dropped["covers"],
        ),
        warnings=warnings,
    )
