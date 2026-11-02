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

"""Who may move a card between boards, where it may go, and the target stage's entry rules."""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from tests.integration.board_api_support import (
    BOARDS,
    make_board,
    make_card,
    ok,
    org_of,
    person,
    put_role,
    stage_id,
)
from tests.integration.board_move_board_support import label, move_board, two_boards
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def test_editing_both_boards_is_needed_and_hidden_boards_stay_hidden(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    two = await two_boards(client, pg_session_factory, visibility="members")
    org = await org_of(pg_session_factory, two.pm)
    editor = await person(pg_session_factory, org)
    await put_role(client, two.pm, two.src, editor.id, "editor")
    card = await make_card(client, two.pm, two.src)

    # No role on a members-only target: it doesn't exist for them.
    assert (await move_board(client, editor, two.src, card, two.dst)).status_code == 404
    await put_role(client, two.pm, two.dst, editor.id, "viewer")
    assert (await move_board(client, editor, two.src, card, two.dst)).status_code == 403
    # Editing the target but only viewing the source.
    await put_role(client, two.pm, two.dst, editor.id, "editor")
    await put_role(client, two.pm, two.src, editor.id, "viewer")
    assert (await move_board(client, editor, two.src, card, two.dst)).status_code == 403

    foreign = await person(pg_session_factory, await new_org(pg_session_factory), "pm")
    elsewhere = (await make_board(client, foreign))["board"]["key"]
    assert (await move_board(client, two.pm, two.src, card, elsewhere)).status_code == 404


async def test_delivery_the_same_board_archived_boards_and_foreign_stages_are_refused(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    two = await two_boards(client, pg_session_factory)
    card = await make_card(client, two.pm, two.src)
    to_delivery = await move_board(client, two.pm, two.src, card, "bud")
    assert to_delivery.status_code == 422
    assert to_delivery.json()["detail"] == "Moving a card to Delivery is a handover."
    assert (await move_board(client, two.pm, two.src, card, two.src)).status_code == 422
    alien = stage_id(two.source, "Done")
    refused = await move_board(client, two.pm, two.src, card, two.dst, stage_id=alien)
    assert refused.status_code == 404

    ok(await client.post(f"{BOARDS}/{two.dst}/archive", headers=two.pm.headers))
    assert (await move_board(client, two.pm, two.src, card, two.dst)).status_code == 409
    ok(await client.post(f"{BOARDS}/{two.dst}/restore", headers=two.pm.headers))
    ok(await client.post(f"{BOARDS}/{two.src}/archive", headers=two.pm.headers))
    assert (await move_board(client, two.pm, two.src, card, two.dst)).status_code == 409


async def test_the_target_stages_rules_apply_to_the_card_as_it_arrives(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    two = await two_boards(client, pg_session_factory)
    doing = stage_id(two.target, "In progress")
    url = f"{BOARDS}/{two.dst}/stages/{doing}"
    rule = {"required_fields": ["label", "due_date"]}
    ok(await client.patch(url, json=rule, headers=two.pm.headers))
    only_here = await label(client, two.pm, two.src, "Local")
    card = await make_card(
        client, two.pm, two.src, due_at="2030-01-01T00:00:00Z", label_ids=[only_here]
    )
    # Its label has no namesake on the target, so it would arrive without one.
    refused = await move_board(client, two.pm, two.src, card, two.dst, stage_id=doing)
    assert refused.status_code == 422
    assert refused.json()["code"] == "STAGE_REQUIREMENTS_MISSING"
    assert refused.json()["missing"] == ["label"]
    await label(client, two.pm, two.dst, "LOCAL")
    assert ok(await move_board(client, two.pm, two.src, card, two.dst, stage_id=doing))

    listed = await make_card(client, two.pm, two.src, "With steps")
    steps = f"{BOARDS}/{two.src}/cards/{listed['number']}/checklist"
    ok(await client.post(steps, json={"text": "step"}, headers=two.pm.headers), 201)
    done = stage_id(two.target, "Done")
    held = await move_board(client, two.pm, two.src, listed, two.dst, stage_id=done)
    assert held.status_code == 409 and held.json()["code"] == "CHECKLIST_OPEN"
    moved = ok(
        await move_board(
            client, two.pm, two.src, listed, two.dst, stage_id=done, confirm_open_checklist=True
        )
    )
    assert moved["stage_id"] == done and moved["completed_at"] is not None


async def test_concurrent_moves_and_creates_get_distinct_numbers(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    two = await two_boards(client, pg_session_factory)
    cards = [await make_card(client, two.pm, two.src, f"Card {n}") for n in range(4)]
    results = await asyncio.gather(
        *(move_board(client, two.pm, two.src, card, two.dst) for card in cards),
        *(
            client.post(f"{BOARDS}/{two.dst}/cards", json={"title": "New"}, headers=two.pm.headers)
            for _ in range(2)
        ),
    )
    assert all(r.status_code in (200, 201) for r in results), [r.text for r in results]
    numbers = sorted(r.json()["number"] for r in results)
    assert numbers == list(range(1, 7))
