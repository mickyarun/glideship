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


"""Hostile or oversized Trello data: cleaned text, dropped links, cheap refusals."""

import json

import pytest

from app.config import settings
from app.models.board_card_detail import EXTERNAL_LABEL_LENGTH
from app.services.boards.constants import COMMENT_MAX_CHARS
from app.services.imports.errors import ImportSourceDataError
from app.services.imports.text import clean_text, http_url
from app.services.imports.trello.cards import card_drafts
from app.services.imports.trello.mapper import author_label
from app.services.imports.trello.models import TrelloExport
from app.services.imports.trello.parse import compact_json, load_compact, parse_board, parse_export
from tests.services.trello_fixture import (
    ANCIENT,
    FIRST,
    IN_FLIGHT,
    OLD,
    SPEC,
    fixture_bytes,
    fixture_json,
)


def test_control_bidi_and_nul_characters_are_stripped_from_every_text() -> None:
    raw = fixture_json()
    spec = next(c for c in raw["cards"] if c["id"] == SPEC)
    spec["name"] = "Wri\u0000te‮ the\x07 spec"
    spec["desc"] = "line one\nline\ttwo⁦"
    raw["labels"][0]["name"] = "B‏ug"
    raw["checklists"][0]["checkItems"][0]["name"] = "Dr\u0000aft"
    raw["actions"][3]["data"]["text"] = "Looks\u0000 good"
    draft = next(d for d in card_drafts(parse_board(raw)) if d.id == SPEC)
    assert draft.title == "Write the spec"
    assert draft.description == "line one\nline\ttwo"
    assert [line.text for line in draft.checklist][:1] == ["Draft"]
    assert draft.comments[0].text == "Looks good"
    assert parse_board(raw).labels[0].name == "Bug"


def test_a_long_author_name_is_cut_to_fit_its_column() -> None:
    label = author_label("A" * 1000)
    assert len(label) <= EXTERNAL_LABEL_LENGTH and label.endswith(" (Trello)")


def test_links_other_than_http_are_dropped() -> None:
    assert http_url("https://trello.com/c/x") == "https://trello.com/c/x"
    for bad in ("javascript:alert(1)", "data:text/html,x", "ftp://x", "//x", "https://", ""):
        assert http_url(bad) is None, bad
    raw = fixture_json()
    raw["cards"][0]["url"] = "javascript:alert(1)"
    raw["cards"][0]["shortLink"] = "../evil"
    draft = next(d for d in card_drafts(parse_board(raw)) if d.id == SPEC)
    assert draft.url is None and draft.source_key == ""
    assert clean_text("ok") == "ok"


def test_a_comment_cut_at_the_cap_counts_as_dropped() -> None:
    raw = fixture_json()
    raw["actions"][3]["data"]["text"] = "x" * (COMMENT_MAX_CHARS + 10)
    draft = next(d for d in card_drafts(parse_board(raw)) if d.id == SPEC)
    assert len(draft.comments[0].text) == COMMENT_MAX_CHARS
    assert draft.dropped["comments_truncated"] == 1


def test_cards_in_an_archived_list_count_as_archived() -> None:
    drafts = {d.id: d for d in card_drafts(parse_export(fixture_bytes()))}
    # ANCIENT is open, but its list ("Old ideas") is archived.
    assert drafts[ANCIENT].closed and drafts[ANCIENT].group_id == OLD
    assert not drafts[IN_FLIGHT].closed


def test_a_position_that_isnt_a_number_sorts_last() -> None:
    raw = fixture_json()
    first = next(c for c in raw["cards"] if c["id"] == FIRST)
    assert [d.id for d in card_drafts(parse_board(raw))][:2] == [FIRST, SPEC]
    first["pos"] = "top"  # FIRST had the lowest position in Backlog
    assert [d.id for d in card_drafts(parse_board(raw))][:2] == [SPEC, FIRST]
    raw["lists"][0]["pos"] = None
    # Backlog's cards now come after every list with a real position.
    assert [d.id for d in card_drafts(parse_board(raw))][-2:] == [SPEC, FIRST]


def test_the_compact_form_reads_back_the_same_board() -> None:
    export = parse_export(fixture_bytes())
    data = compact_json(export)
    assert len(data) < len(fixture_bytes())
    assert load_compact(data) == export
    assert card_drafts(load_compact(data)) == card_drafts(export)


@pytest.mark.parametrize(
    ("key", "setting"),
    [
        ("cards", "import_max_cards"),
        ("actions", "import_max_actions"),
        ("lists", "import_max_lists"),
        ("members", "import_max_members"),
        ("labels", "import_max_labels"),
        ("checklists", "import_max_checklists"),
    ],
)
def test_arrays_over_their_cap_are_refused_before_any_model_is_built(
    key: str, setting: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = fixture_json()
    monkeypatch.setattr(settings.boards, setting, len(raw[key]) - 1)

    def never(*_: object, **__: object) -> None:
        raise AssertionError("validated an oversized board")

    monkeypatch.setattr(TrelloExport, "model_validate", never)
    with pytest.raises(ImportSourceDataError, match="too big"):
        parse_export(json.dumps(raw).encode())


def test_checklist_lines_are_counted_across_checklists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.boards, "import_max_check_items", 2)
    with pytest.raises(ImportSourceDataError, match="checklist items"):
        parse_export(fixture_bytes())


@pytest.mark.parametrize(
    "raw",
    [
        b"[" * 100_000 + b"]" * 100_000,  # too deep: RecursionError
        b'{"lists": [], "cards": [], "n": ' + b"9" * 5000 + b"}",  # too many digits: ValueError
    ],
)
def test_hostile_json_reads_as_not_a_board(raw: bytes) -> None:
    with pytest.raises(ImportSourceDataError, match="isn't a Trello board"):
        parse_export(raw)
