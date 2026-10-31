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

"""Helpers for the handover tests: a product board with handover on, and its people.

``Desk`` is an org with a PM (board admin, the one handing over), a designer
and a tech lead (the owners auto-assignment picks for design and the tech
plan), and a board made from the product template with handover on.
``stubbed`` replaces the model, embedding and agent calls; ``spawn`` records
which stage agents were asked for.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient, Response
from sqlalchemy import select

from app.models.board_card import BoardCard
from app.models.bud import BUDTimelineEvent
from app.models.bud_version import BUDVersion
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    make_board,
    make_card,
    ok,
    person,
    stage_id,
)
from tests.integration.bud_lifecycle_support import stub_externals
from tests.integration.scan_features_bugs_support import Factory, new_org

ALL_PHASES = {"bud": True, "design": True, "tech_arch": True, "testing": True}


@dataclass(frozen=True)
class Desk:
    """One org's people and its handover board."""

    org: uuid.UUID
    pm: Person
    designer: Person
    lead: Person
    board: dict[str, Any]

    @property
    def key(self) -> str:
        """The board's key."""
        return str(self.board["board"]["key"])

    def stage(self, name: str) -> str:
        """The id of one of the board's stages."""
        return stage_id(self.board, name)


async def desk(client: AsyncClient, factory: Factory, *, handover: bool = True) -> Desk:
    """A fresh org and product board; handover on unless ``handover`` is False."""
    org = await new_org(factory)
    pm = await person(factory, org, "pm")
    designer = await person(factory, org, "designer")
    lead = await person(factory, org, "tech_lead")
    board = await make_board(client, pm, template="product")
    if handover:
        url = f"{BOARDS}/{board['board']['key']}"
        ok(await client.patch(url, json={"handover_enabled": True}, headers=pm.headers))
    return Desk(org, pm, designer, lead, board)


async def card(client: AsyncClient, d: Desk, title: str = "Pricing page", **body: Any) -> str:
    """A card on the desk's board; its url."""
    made = await make_card(client, d.pm, d.key, title, **body)
    return f"{BOARDS}/{d.key}/cards/{made['number']}"


@contextmanager
def stubbed(vector: list[float] | None = None) -> Iterator[AsyncMock]:
    """Model and embedding stubs, and the stage-agent spawn recorded."""
    spawn = AsyncMock(return_value=None)
    with ExitStack() as stack:
        stack.enter_context(stub_externals(vector))
        for where in ("app.services.bud_stage_jobs", "app.services.bud_create"):
            stack.enter_context(patch(f"{where}.create_agent_task_for_stage", spawn))
        yield spawn


async def hand_over(
    client: AsyncClient, who: Person, url: str, *, key: uuid.UUID | None = None, **body: Any
) -> Response:
    """POST a confirm (a fresh idempotency key unless one is given)."""
    payload = {"idempotency_key": str(key or uuid.uuid4()), **body}
    return await client.post(f"{url}/handovers", json=payload, headers=who.headers)


async def preview(client: AsyncClient, who: Person, url: str, **body: Any) -> Response:
    """POST a preview."""
    return await client.post(f"{url}/handovers/preview", json=body, headers=who.headers)


def spawned_stages(spawn: AsyncMock) -> list[str]:
    """The stage of every agent asked for."""
    return [call.args[1] for call in spawn.await_args_list]


async def status_changes(factory: Factory, bud_id: uuid.UUID) -> list[tuple[Any, ...]]:
    """``(from, to, via, actor)`` of each status change, oldest first."""
    async with factory() as db:
        rows = await db.scalars(
            select(BUDTimelineEvent)
            .where(
                BUDTimelineEvent.bud_id == bud_id,
                BUDTimelineEvent.event_type == "status_change",
            )
            .order_by(BUDTimelineEvent.created_at)
        )
        return [(r.detail["from"], r.detail["to"], r.detail.get("via"), r.actor_id) for r in rows]


async def first_editor(factory: Factory, bud_id: uuid.UUID) -> uuid.UUID | None:
    """The earliest ``bud_versions`` row's editor: who the BUD is attributed to."""
    async with factory() as db:
        editor: uuid.UUID | None = await db.scalar(
            select(BUDVersion.edited_by)
            .where(BUDVersion.bud_id == bud_id)
            .order_by(BUDVersion.edited_at)
            .limit(1)
        )
        return editor


async def card_stage(factory: Factory, card_id: str) -> uuid.UUID:
    """The stage a card is in now."""
    async with factory() as db:
        found = await db.get(BoardCard, uuid.UUID(card_id))
        assert found is not None
        return found.stage_id
