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

"""Trello names onto ours: categories, colours, people, card drafts and the review summary."""

import json
import uuid

import pytest

from app.models.board_enums import BoardLabelColor, BoardStageCategory
from app.models.external_import import ImportMode
from app.schemas.boards.trello_discovery import TrelloWarning
from app.services.boards.constants import CHECKLIST_MAX_ITEMS
from app.services.imports.draft import ChecklistLine
from app.services.imports.trello.cards import card_drafts
from app.services.imports.trello.constants import (
    TRELLO_DEFAULT_LABEL_COLOR,
    TRELLO_EXPORT_ACTION_CAP,
)
from app.services.imports.trello.discovery import build_discovery
from app.services.imports.trello.mapper import (
    author_label,
    label_name,
    nearest_label_color,
    suggest_category,
    suggest_users,
)
from app.services.imports.trello.models import TrelloLabel
from app.services.imports.trello.parse import parse_board, parse_export
from tests.services.trello_fixture import (
    ANCIENT,
    ARCHIVED,
    DONE_THING,
    FIRST,
    IN_FLIGHT,
    OLD,
    PRIYA,
    SAM,
    SPEC,
    fixture_bytes,
    fixture_json,
)

TODO, IN_PROGRESS = BoardStageCategory.TODO, BoardStageCategory.IN_PROGRESS
DONE, CANCELED = BoardStageCategory.DONE, BoardStageCategory.CANCELED


@pytest.mark.parametrize(
    ("name", "is_last", "expected"),
    [
        ("Backlog", False, TODO),
        ("Doing", False, IN_PROGRESS),
        ("In Progress", False, IN_PROGRESS),
        ("Under review", True, IN_PROGRESS),
        ("Writing", False, IN_PROGRESS),
        ("Done", False, DONE),
        ("Completed ✅", False, DONE),
        ("Published", False, DONE),
        ("Won't do", False, CANCELED),
        ("Ideas", True, DONE),
        ("Ideas", False, TODO),
        ("Unreviewed", False, TODO),
    ],
)
def test_list_names_hint_their_category(
    name: str, is_last: bool, expected: BoardStageCategory
) -> None:
    assert suggest_category(name, is_last=is_last) is expected


@pytest.mark.parametrize(
    ("color", "expected"),
    [
        ("green", BoardLabelColor.GREEN),
        ("green_dark", BoardLabelColor.GREEN),
        ("sky_light", BoardLabelColor.SKY),
        ("BLACK", BoardLabelColor.BLACK),
        (None, TRELLO_DEFAULT_LABEL_COLOR),
        ("chartreuse", TRELLO_DEFAULT_LABEL_COLOR),
    ],
)
def test_colours_map_to_the_nearest_palette_entry(
    color: str | None, expected: BoardLabelColor
) -> None:
    assert nearest_label_color(color) is expected


def test_unnamed_labels_take_their_colour_name_and_authors_get_a_label() -> None:
    assert label_name(TrelloLabel(id="x", name="  ", color="purple_light")) == "Purple"
    assert label_name(TrelloLabel(id="x", name="Bug", color="red")) == "Bug"
    assert author_label("Sam Outsider") == "Sam Outsider (Trello)"
    assert author_label(" ") == "Someone (Trello)"


def test_members_match_one_person_by_full_name_only() -> None:
    priya, twin_a, twin_b = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    people = [(priya, "priya  SHARMA"), (twin_a, "Alex Kim"), (twin_b, "Alex Kim")]
    names = {"m1": "Priya Sharma", "m2": "Alex Kim", "m3": "Nobody", "m4": ""}
    assert suggest_users(names, people) == {"m1": priya, "m2": None, "m3": None, "m4": None}


def test_cards_come_in_list_then_position_order_with_their_parts() -> None:
    drafts = card_drafts(parse_export(fixture_bytes()))
    assert [d.id for d in drafts] == [FIRST, SPEC, IN_FLIGHT, ARCHIVED, DONE_THING, ANCIENT]
    spec = drafts[1]
    assert spec.checklist == [
        ChecklistLine("Launch", "Draft", True),
        ChecklistLine("Launch", "Review", False),
        ChecklistLine("QA", "Test it", False),
    ]
    # Oldest comment first, with the Trello author kept for mapping.
    assert [(c.text, c.member_id) for c in spec.comments] == [
        ("Looks good", PRIYA),
        ("From someone not in the org", SAM),
    ]
    assert spec.dropped == {"custom_fields": 1}
    assert drafts[2].dropped == {"covers": 1} and drafts[4].dropped == {"power_up_data": 1}
    assert drafts[0].description is None and spec.description is not None
    assert "<script>" in spec.description  # kept raw: the frontend sanitises on render


def test_long_checklists_are_capped_and_counted() -> None:
    raw = fixture_json()
    raw["checklists"] = [
        {
            "id": "k1",
            "idCard": SPEC,
            "name": "Big",
            "checkItems": [{"id": f"i{n}", "name": f"Item {n}", "pos": n} for n in range(105)],
        }
    ]
    spec = next(d for d in card_drafts(parse_board(raw)) if d.id == SPEC)
    assert len(spec.checklist) == CHECKLIST_MAX_ITEMS
    assert spec.dropped["checklist_items"] == 105 - CHECKLIST_MAX_ITEMS


def test_discovery_suggests_stages_people_and_warns_at_the_action_cap() -> None:
    export = parse_export(fixture_bytes())
    priya = uuid.uuid4()
    found = build_discovery(
        export, card_drafts(export), [(priya, "Priya Sharma")], ImportMode.UPLOAD
    )
    lists = {lst.name: lst for lst in found.lists}
    assert lists["Backlog"].suggested_category is TODO
    assert lists["Doing"].suggested_category is IN_PROGRESS
    assert lists["Done"].suggested_category is DONE and lists["Done"].card_count == 2
    assert lists["Old ideas"].suggested_skip and lists["Old ideas"].id == OLD
    assert {m.id: m.suggested_user_id for m in found.members} == {PRIYA: priya, SAM: None}
    assert {lb.name: lb.mapped_color for lb in found.labels}[
        "Design"
    ] is TRELLO_DEFAULT_LABEL_COLOR
    # The closed card, and the card in the archived list.
    assert found.counts.cards == 6 and found.counts.archived_cards == 2
    assert found.counts.comments == 3 and found.counts.checklist_items == 3
    assert (found.dropped.custom_fields, found.dropped.power_up_data, found.dropped.covers) == (
        1,
        1,
        1,
    )
    assert found.warnings == []

    raw = fixture_json()
    raw["actions"] = [
        {"id": f"a{i}", "type": "updateCard"} for i in range(TRELLO_EXPORT_ACTION_CAP)
    ]
    capped = parse_export(json.dumps(raw).encode())
    upload = build_discovery(capped, card_drafts(capped), [], ImportMode.UPLOAD)
    assert upload.warnings == [TrelloWarning.ACTION_CAP]
    # API mode pages every comment, so the cap doesn't apply.
    assert build_discovery(capped, card_drafts(capped), [], ImportMode.API).warnings == []
