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

"""Helpers for the send-back, re-handover, delivered and chip tests."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select, update

from app.models.board_card_detail import BoardCardComment, BoardCardEvent
from app.models.board_enums import BoardCardEventType
from app.models.bud import BUDDocument, BUDStatus
from app.services import event_bus
from tests.integration.board_api_support import Person, ok
from tests.integration.board_handover_support import Desk, hand_over, stubbed
from tests.integration.bud_lifecycle_support import written_sections
from tests.integration.scan_features_bugs_support import Factory

BUDS = "/api/v1/buds"
# A BUD title nobody on the board side may read.
SECRET_TITLE = "Secret engineering title"


async def handed(client: AsyncClient, who: Person, url: str, **body: Any) -> dict[str, Any]:
    """A confirmed handover's body (agents stubbed)."""
    with stubbed():
        return dict(ok(await hand_over(client, who, url, **body), 201))


def bud_of(result: dict[str, Any]) -> uuid.UUID:
    """The BUD a handover result names."""
    return uuid.UUID(result["handover"]["bud_id"])


async def send_back(
    client: AsyncClient, who: Person, bud_id: uuid.UUID, reason: str = "Scope is wrong"
) -> Response:
    """POST a send-back."""
    url = f"{BUDS}/{bud_id}/return-to-board"
    with stubbed():
        return await client.post(url, json={"reason": reason}, headers=who.headers)


async def set_status(factory: Factory, bud_id: uuid.UUID, status: BUDStatus) -> None:
    """Move a BUD in the database, as dev work would have, writing what the stage needs."""
    async with factory() as db:
        bud = await db.get(BUDDocument, bud_id)
        assert bud is not None
        written = written_sections(
            status, requirements_md=bud.requirements_md, tech_spec_md=bud.tech_spec_md
        )
        await db.execute(
            update(BUDDocument).where(BUDDocument.id == bud_id).values(status=status, **written)
        )
        await db.commit()


async def card_events(
    factory: Factory, card_id: str, kind: BoardCardEventType
) -> list[dict[str, Any]]:
    """The details of a card's events of one kind, oldest first."""
    async with factory() as db:
        rows = await db.scalars(
            select(BoardCardEvent)
            .where(BoardCardEvent.card_id == uuid.UUID(card_id), BoardCardEvent.type == kind)
            .order_by(BoardCardEvent.created_at, BoardCardEvent.id)
        )
        return [dict(r.detail) for r in rows]


async def card_comments(factory: Factory, card_id: str) -> list[BoardCardComment]:
    """A card's comments, oldest first."""
    async with factory() as db:
        rows = await db.scalars(
            select(BoardCardComment)
            .where(BoardCardComment.card_id == uuid.UUID(card_id))
            .order_by(BoardCardComment.created_at)
        )
        return list(rows)


@asynccontextmanager
async def board_events(d: Desk) -> AsyncIterator[list[dict[str, Any]]]:
    """Every message the desk's board topic publishes inside the block."""
    topic = f"board:{d.board['board']['id']}"
    queue = event_bus.subscribe(topic)
    seen: list[dict[str, Any]] = []
    try:
        yield seen
        await asyncio.sleep(0)
        while not queue.empty():
            seen.append(queue.get_nowait()["data"])
    finally:
        event_bus.unsubscribe(topic, queue)
