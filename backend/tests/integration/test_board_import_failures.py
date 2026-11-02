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


"""Odd and failing cards: cleaned on the way in, recorded, numbered without gaps, retried."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.models.board import Board
from app.models.board_card_detail import EXTERNAL_LABEL_LENGTH, BoardCardComment
from app.models.external_import import ExternalItemMap, ExternalItemStatus
from app.services.boards.errors import BoardRuleError
from app.services.imports import card_writer
from app.services.imports.context import ImportContext
from tests.integration.board_api_support import BOARDS, ok
from tests.integration.board_import_support import (
    IMPORTS,
    Jobs,
    board_cards,
    capture_jobs,
    mapping,
    named,
    new_board,
    save_and_start,
    start_url,
    upload,
    use_import_storage,
)
from tests.integration.board_support import board_key
from tests.integration.scan_features_bugs_support import Factory, new_org
from tests.services.trello_fixture import BACKLOG, DOING, DONE, IN_FLIGHT, OLD, SPEC, fixture_json

pytestmark = pytest.mark.integration


@pytest.fixture
def jobs(pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Jobs:
    use_import_storage(tmp_path, monkeypatch)
    return capture_jobs(pg_session_factory, monkeypatch)


async def _imported(
    client: AsyncClient, factory: Factory, jobs: Jobs, raw: dict[str, Any]
) -> tuple[Any, dict[str, Any]]:
    """Upload ``raw``, map it onto a new board, run it; returns the PM and the session."""
    org = await new_org(factory)
    pm = await named(factory, org, "Pat Manager", "pm")
    accepted = ok(await upload(client, pm, json.dumps(raw).encode()), 202)
    await jobs.run_all()
    session_id = str(accepted["sessionId"])
    await save_and_start(client, pm, session_id, mapping(new_board(board_key())))
    await jobs.run_all()
    return pm, ok(await client.get(f"{IMPORTS}/{session_id}", headers=pm.headers))


async def test_a_card_with_a_huge_author_name_and_nul_bytes_is_cleaned_and_imported(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs
) -> None:
    raw = fixture_json()
    spec = next(c for c in raw["cards"] if c.get("id") == SPEC)
    spec["name"] = "Bad\u0000 na‮me"
    spec["desc"] = "keeps\nlines\u0000"
    comment = next(a for a in raw["actions"] if a["data"].get("text") == "Looks good")
    comment["idMemberCreator"] = "5f00000000000000000m0099"  # nobody on the board
    comment["memberCreator"] = {"id": "5f00000000000000000m0099", "fullName": "N" * 5000}
    comment["data"]["text"] = "Looks\u0000 good"
    _, done = await _imported(client, pg_session_factory, jobs, raw)
    assert done["status"] == "completed" and done["result"]["imported"] == 5
    cards = {c.title: c for c in await board_cards(pg_session_factory, done["board_id"])}
    card = cards["Bad name"]
    assert card.description_md == "keeps\nlines"
    async with pg_session_factory() as db:
        comments = list(
            await db.scalars(select(BoardCardComment).where(BoardCardComment.card_id == card.id))
        )
    long_one = next(c for c in comments if c.body == "Looks good")
    assert long_one.author_label is not None
    assert len(long_one.author_label) <= EXTERNAL_LABEL_LENGTH
    assert long_one.author_label.endswith(" (Trello)")


async def test_a_failing_card_is_recorded_numbers_stay_contiguous_and_a_resume_retries_it(
    client: AsyncClient,
    pg_session_factory: Factory,
    jobs: Jobs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write = card_writer.write_card
    broken = {"on": True}

    async def fail_in_flight(*args: Any) -> uuid.UUID:
        card_id = await write(*args)  # the card is written and takes a number...
        if broken["on"] and args[2].id == IN_FLIGHT:
            # ...then its savepoint rolls back.
            raise BoardRuleError("Trello sent something odd.")
        return card_id

    monkeypatch.setattr(card_writer, "write_card", fail_in_flight)
    pm, done = await _imported(client, pg_session_factory, jobs, fixture_json())
    assert done["status"] == "failed" and done["error"].startswith("1 cards couldn't")
    assert (done["result"]["imported"], done["result"]["failed"]) == (4, 1)
    cards = await board_cards(pg_session_factory, done["board_id"])
    assert [c.number for c in cards] == [1, 2, 3, 4]
    async with pg_session_factory() as db:
        board = await db.get(Board, uuid.UUID(done["board_id"]))
        assert board is not None and board.next_card_number == 5
        row = await db.scalar(
            select(ExternalItemMap).where(
                ExternalItemMap.session_id == uuid.UUID(done["id"]),
                ExternalItemMap.external_id == IN_FLIGHT,
            )
        )
        assert row is not None and row.status is ExternalItemStatus.FAILED
        assert row.error == "Trello sent something odd."
    # Only cards that landed count what they dropped: Write the spec's one
    # unmapped member, not In flight's two.
    assert done["result"]["dropped"]["unmapped_assignees"] == 1

    broken["on"] = False
    ok(await client.post(start_url(done["id"]), headers=pm.headers), 202)
    await jobs.run_all()
    again = ok(await client.get(f"{IMPORTS}/{done['id']}", headers=pm.headers))
    assert again["status"] == "completed" and again["error"] is None
    assert (again["result"]["imported"], again["result"]["failed"]) == (5, 0)
    assert again["result"]["already_imported"] == 0
    assert again["result"]["dropped"]["unmapped_assignees"] == 3  # In flight's two join
    cards = await board_cards(pg_session_factory, done["board_id"])
    assert [c.number for c in cards] == [1, 2, 3, 4, 5]
    assert cards[-1].title == "In flight"


async def test_a_board_of_120_cards_lands_in_three_batches(
    client: AsyncClient,
    pg_session_factory: Factory,
    jobs: Jobs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings.boards, "import_batch_size", 50)
    raw = fixture_json()
    raw["cards"] = [
        {"id": f"{n:024x}", "name": f"Card {n}", "idList": BACKLOG, "pos": n} for n in range(120)
    ]
    raw["checklists"], raw["actions"] = [], []
    commits: Counter[str] = Counter()
    commit = ImportContext.commit_batch

    async def counted(self: ImportContext) -> None:
        commits["batches"] += 1
        await commit(self)

    monkeypatch.setattr(ImportContext, "commit_batch", counted)
    _, done = await _imported(client, pg_session_factory, jobs, raw)
    assert done["status"] == "completed" and done["result"]["imported"] == 120
    assert (done["processed_count"], done["last_processed_index"]) == (120, 119)
    # Three batches (50, 50, 20) and the closing summary.
    assert commits["batches"] == 4
    cards = await board_cards(pg_session_factory, done["board_id"])
    assert [c.number for c in cards] == list(range(1, 121))
    assert [c.title for c in cards][:2] == ["Card 0", "Card 1"]


async def test_a_card_deleted_after_import_comes_back_on_the_next_import(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs
) -> None:
    pm, done = await _imported(client, pg_session_factory, jobs, fixture_json())
    spec = next(
        c for c in await board_cards(pg_session_factory, done["board_id"]) if c.number == 2
    )
    async with pg_session_factory() as db:
        await db.delete(await db.get(type(spec), spec.id))
        await db.commit()
    again = ok(await upload(client, pm), 202)
    await jobs.run_all()
    key = done["board_key"]
    stages = ok(await client.get(f"{BOARDS}/{key}", headers=pm.headers))["stages"]
    by_name = {s["name"]: s["id"] for s in stages}
    groups = [
        {"group_id": g, "action": "existing", "stage_id": by_name[n]}
        for g, n in ((BACKLOG, "Backlog"), (DOING, "Doing"), (DONE, "Done"))
    ]
    body = mapping(
        {"kind": "existing", "key": key}, groups=[*groups, {"group_id": OLD, "action": "skip"}]
    )
    await save_and_start(client, pm, str(again["sessionId"]), body)
    await jobs.run_all()
    read = ok(await client.get(f"{IMPORTS}/{again['sessionId']}", headers=pm.headers))
    assert (read["result"]["imported"], read["result"]["already_imported"]) == (1, 4)
