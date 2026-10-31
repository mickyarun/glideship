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

"""Finding a card by key: live keys first, then old keys, checked on the card's current board."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from app.models.board_card import BoardCardKeyAlias
from tests.integration.board_api_support import BOARDS, make_board, make_card, ok, person, put_role
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration

BY_KEY = f"{BOARDS}/cards/by-key"


async def _alias(
    factory: Factory, org: uuid.UUID, board: dict[str, Any], number: int, card_id: str
) -> None:
    async with factory() as db:
        db.add(
            BoardCardKeyAlias(
                org_id=org,
                board_id=uuid.UUID(board["board"]["id"]),
                number=number,
                card_id=uuid.UUID(card_id),
            )
        )
        await db.commit()


async def test_live_keys_resolve_in_any_case(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    key = (await make_board(client, pm))["board"]["key"]
    card = await make_card(client, pm, key, "Find me")
    for spelled in (card["key"], card["key"].lower()):
        assert ok(await client.get(f"{BY_KEY}/{spelled}", headers=pm.headers))["id"] == card["id"]
    for missing in (f"{key}-99", "NOPE-1", "garbage"):
        assert (await client.get(f"{BY_KEY}/{missing}", headers=pm.headers)).status_code == 404


async def test_an_old_key_opens_the_card_only_for_people_on_its_current_board(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, other = await new_org(pg_session_factory), await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    member, outsider = [await person(pg_session_factory, org) for _ in range(2)]
    hidden = (await make_board(client, pm, visibility="members"))["board"]["key"]
    await put_role(client, pm, hidden, member.id, "viewer")
    card = await make_card(client, pm, hidden, "Moved here")
    # The card used to be number 7 on a board everyone could see.
    old = await make_board(client, pm)
    await _alias(pg_session_factory, org, old, 7, card["id"])
    old_key = f"{old['board']['key']}-7"

    assert (
        ok(await client.get(f"{BY_KEY}/{old_key}", headers=member.headers))["key"] == card["key"]
    )
    lower = old_key.lower()
    assert (await client.get(f"{BY_KEY}/{lower}", headers=outsider.headers)).status_code == 404
    foreigner = await person(pg_session_factory, other, "manager")
    assert (await client.get(f"{BY_KEY}/{old_key}", headers=foreigner.headers)).status_code == 404


async def test_a_live_key_wins_over_an_alias_with_the_same_text(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    board = await make_board(client, pm)
    key = board["board"]["key"]
    live = await make_card(client, pm, key, "Live")
    other = await make_card(client, pm, key, "Other")
    await _alias(pg_session_factory, org, board, live["number"], other["id"])
    assert ok(await client.get(f"{BY_KEY}/{live['key']}", headers=pm.headers))["id"] == live["id"]
