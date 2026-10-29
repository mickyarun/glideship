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

"""Card history: frozen board and categories, and coalesced edits."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.config import settings
from app.models.board import BoardStage
from app.models.board_card_detail import BoardCardEvent
from app.models.board_enums import BoardCardEventType, BoardStageCategory
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    make_board,
    make_card,
    ok,
    person,
    put_role,
    stage_id,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def _setup(client: AsyncClient, factory: Factory) -> tuple[Person, dict[str, Any], str]:
    org = await new_org(factory)
    pm = await person(factory, org, "pm")
    board = await make_board(client, pm, template="ops")
    return pm, board, board["board"]["key"]


async def _move(client: AsyncClient, who: Person, key: str, number: int, **body: Any) -> Any:
    url = f"{BOARDS}/{key}/cards/{number}/move"
    return ok(await client.post(url, json=body, headers=who.headers))


async def _events(factory: Factory, card_id: str) -> list[BoardCardEvent]:
    async with factory() as db:
        rows = await db.scalars(
            select(BoardCardEvent)
            .where(BoardCardEvent.card_id == uuid.UUID(card_id))
            .order_by(BoardCardEvent.created_at, BoardCardEvent.id)
        )
        return list(rows)


async def test_moves_freeze_the_board_and_categories_they_happened_in(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board, key = await _setup(client, pg_session_factory)
    card = await make_card(client, pm, key)
    waiting = stage_id(board, "Waiting")
    await _move(client, pm, key, card["number"], stage_id=waiting)
    # Re-categorising the stage later doesn't rewrite history.
    ok(
        await client.patch(
            f"{BOARDS}/{key}/stages/{waiting}", json={"category": "todo"}, headers=pm.headers
        )
    )
    created, moved = await _events(pg_session_factory, card["id"])
    assert created.type is BoardCardEventType.CREATED
    assert created.to_category is BoardStageCategory.TODO
    assert (moved.type, moved.from_category, moved.to_category) == (
        BoardCardEventType.MOVED,
        BoardStageCategory.TODO,
        BoardStageCategory.IN_PROGRESS,
    )
    assert str(moved.board_id) == board["board"]["id"]
    async with pg_session_factory() as db:
        stage = await db.get(BoardStage, uuid.UUID(waiting))
        assert stage is not None and stage.category is BoardStageCategory.TODO
    history = ok(
        await client.get(f"{BOARDS}/{key}/cards/{card['number']}/events", headers=pm.headers)
    )
    assert [e["type"] for e in history["items"]] == ["moved", "created"]


async def test_edits_by_one_person_coalesce_within_the_window(
    client: AsyncClient, pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    window_seconds = 300
    monkeypatch.setattr(settings.boards, "edit_coalesce_seconds", window_seconds)
    pm, _, key = await _setup(client, pg_session_factory)
    card = await make_card(client, pm, key)
    url = f"{BOARDS}/{key}/cards/{card['number']}"
    ok(await client.patch(url, json={"title": "One"}, headers=pm.headers))
    ok(await client.patch(url, json={"priority": "P2"}, headers=pm.headers))
    ok(await client.patch(url, json={"title": "One"}, headers=pm.headers))  # no change
    edits = [e for e in await _events(pg_session_factory, card["id"]) if e.type == "edited"]
    assert [e.detail["fields"] for e in edits] == [["priority", "title"]]

    async with pg_session_factory() as db:
        window = timedelta(seconds=window_seconds + 1)
        await db.execute(
            update(BoardCardEvent)
            .where(BoardCardEvent.id == edits[0].id)
            .values(created_at=edits[0].created_at - window)
        )
        await db.commit()
    ok(await client.patch(url, json={"description_md": "Later"}, headers=pm.headers))
    other = await person(pg_session_factory, await _org(client, pm))
    await put_role(client, pm, key, other.id, "editor")
    ok(await client.patch(url, json={"title": "Two"}, headers=other.headers))
    edits = [e for e in await _events(pg_session_factory, card["id"]) if e.type == "edited"]
    assert [(e.actor_id, e.detail["fields"]) for e in edits] == [
        (pm.id, ["priority", "title"]),
        (pm.id, ["description_md"]),
        (other.id, ["title"]),
    ]


async def _org(client: AsyncClient, who: Person) -> uuid.UUID:
    return uuid.UUID(ok(await client.get("/api/v1/auth/me", headers=who.headers))["org_id"])
