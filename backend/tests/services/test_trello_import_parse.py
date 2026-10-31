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

"""Reading a Trello export: tolerant of gaps, strict about what a board is."""

import json
from datetime import UTC, datetime

import pytest

from app.services.imports.errors import ImportSourceDataError
from app.services.imports.trello.constants import TRELLO_EXPORT_ACTION_CAP
from app.services.imports.trello.parse import parse_board, parse_export
from tests.services.trello_fixture import ARCHIVED, IN_FLIGHT, SPEC, fixture_bytes


def test_the_fixture_parses_with_every_part() -> None:
    export = parse_export(fixture_bytes())
    assert (len(export.lists), len(export.labels), len(export.members)) == (4, 3, 2)
    # The card without an id is left out rather than failing the file.
    assert len(export.cards) == 6
    assert len(export.comments()) == 3 and len(export.actions) == 4
    assert not export.action_cap_hit
    cards = {c.id: c for c in export.cards}
    spec = cards[SPEC]
    assert spec.due == datetime(2026, 11, 5, 17, tzinfo=UTC)
    assert spec.start == datetime(2026, 11, 1, 9, tzinfo=UTC)
    assert len(spec.attachments) == 3 and spec.attachments[1].is_upload
    assert len(spec.custom_field_items) == 1
    # Bad or null values read as empty.
    assert cards[IN_FLIGHT].start is None and cards[IN_FLIGHT].due_complete
    assert cards[ARCHIVED].closed and cards[ARCHIVED].id_labels == []


def test_missing_keys_and_nulls_read_as_empty() -> None:
    export = parse_board(
        {
            "lists": [{"id": "l1", "name": None, "pos": "top"}],
            "cards": [{"id": "c1", "idLabels": None, "due": 12, "closed": "yes"}],
            "actions": None,
            "members": [{"id": "m1"}, "not a member"],
        }
    )
    assert export.lists[0].name == "" and export.lists[0].pos == 0.0
    card = export.cards[0]
    assert card.id_labels == [] and card.due is None and card.closed is False
    assert export.actions == [] and [m.id for m in export.members] == ["m1"]


@pytest.mark.parametrize(
    "raw",
    [b"not json", b"[1, 2]", b'{"name": "no lists or cards"}', b"\xff\xfe", b'{"lists": 1}'],
)
def test_anything_but_a_board_is_refused(raw: bytes) -> None:
    with pytest.raises(ImportSourceDataError):
        parse_export(raw)


def test_an_export_at_the_action_cap_says_comments_are_missing() -> None:
    actions = [{"id": f"a{i}", "type": "updateCard"} for i in range(TRELLO_EXPORT_ACTION_CAP)]
    export = parse_export(json.dumps({"lists": [], "cards": [], "actions": actions}).encode())
    assert export.action_cap_hit
    assert not parse_board({"lists": [], "cards": [], "actions": actions[:-1]}).action_cap_hit
