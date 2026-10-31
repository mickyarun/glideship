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


"""What a move between boards tells people who can see only one side of it."""

from __future__ import annotations

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
BY_KEY = f"{BOARDS}/cards/by-key"


async def test_a_viewer_of_only_the_source_cannot_follow_the_card(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    two = await two_boards(client, pg_session_factory, visibility="members")
    org = await org_of(pg_session_factory, two.pm)
    watcher = await person(pg_session_factory, org)
    await put_role(client, two.pm, two.src, watcher.id, "viewer")
    card = await make_card(client, two.pm, two.src)
    moved = ok(await move_board(client, two.pm, two.src, card, two.dst))

    # The old key and the new one look exactly like keys that never existed.
    never = await client.get(f"{BY_KEY}/{two.src}-9999", headers=watcher.headers)
    for key in (card["key"], moved["key"]):
        hidden = await client.get(f"{BY_KEY}/{key}", headers=watcher.headers)
        assert hidden.status_code == never.status_code == 404
        assert hidden.content == never.content
    # The old deep link is gone for everyone; by-key still finds it for the mover.
    old = await client.get(f"{BOARDS}/{two.src}/cards/{card['number']}", headers=two.pm.headers)
    assert old.status_code == 404
    found = ok(await client.get(f"{BY_KEY}/{card['key']}", headers=two.pm.headers))
    assert found["key"] == moved["key"]


async def test_a_stage_from_another_orgs_board_is_not_found(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    two = await two_boards(client, pg_session_factory)
    foreign = await person(pg_session_factory, await new_org(pg_session_factory), "pm")
    elsewhere = await make_board(client, foreign)
    card = await make_card(client, two.pm, two.src)
    alien = stage_id(elsewhere, "Done")
    refused = await move_board(client, two.pm, two.src, card, two.dst, stage_id=alien)
    assert refused.status_code == 404 and refused.json()["detail"] == "Stage not found."


async def test_history_hides_a_members_only_source_from_people_outside_it(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    secret = (await make_board(client, pm, visibility="members"))["board"]["key"]
    public = (await make_board(client, pm, template="blank", visibility="org"))["board"]["key"]
    member, outsider = await person(pg_session_factory, org), await person(pg_session_factory, org)
    await put_role(client, pm, secret, member.id, "viewer")
    mine = await label(client, pm, secret, "Embargoed")
    card = await make_card(client, pm, secret, "Launch", label_ids=[mine])
    moved = ok(await move_board(client, pm, secret, card, public))
    events = f"{BOARDS}/{public}/cards/{moved['number']}/events"

    def moved_entry(page: dict[str, object]) -> dict[str, object]:
        items = page["items"]
        assert isinstance(items, list)
        (entry,) = [e for e in items if e["type"] == "moved_board"]
        return dict(entry["detail"])

    seen = moved_entry(ok(await client.get(events, headers=member.headers)))
    assert seen["from_board"] is not None and seen["old_key"] == card["key"]
    assert seen["dropped_labels"] == ["Embargoed"]
    assert seen["from_stage"] is not None

    blank = moved_entry(ok(await client.get(events, headers=outsider.headers)))
    assert blank["from_board"] is None and blank["from_stage"] is None
    assert blank["old_key"] is None and blank["cleared_repo"] is None
    assert blank["dropped_labels"] == []
    assert blank["new_key"] == moved["key"]
    assert blank["to_board"] == seen["to_board"]


async def test_history_hides_a_members_only_target_from_people_outside_it(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    seo = (await make_board(client, pm, visibility="members"))["board"]["key"]
    hid = (await make_board(client, pm, template="blank", visibility="members"))["board"]["key"]
    reader, both = await person(pg_session_factory, org), await person(pg_session_factory, org)
    await put_role(client, pm, seo, reader.id, "viewer")
    for key in (seo, hid):
        await put_role(client, pm, key, both.id, "viewer")
    card = await make_card(client, pm, seo, "Round trip")
    away = ok(await move_board(client, pm, seo, card, hid))
    back = ok(await move_board(client, pm, hid, away, seo))
    events = f"{BOARDS}/{seo}/cards/{back['number']}/events"

    async def moved(headers: dict[str, str]) -> list[dict[str, object]]:
        page = ok(await client.get(events, headers=headers))
        return [dict(e["detail"]) for e in reversed(page["items"]) if e["type"] == "moved_board"]

    out, home = await moved(reader.headers)
    assert out["to_board"] is None and out["new_key"] is None
    assert out["from_board"] is not None and out["old_key"] == card["key"]
    assert home["from_board"] is None and home["old_key"] is None
    assert home["from_stage"] is None
    assert home["to_board"] is not None and home["new_key"] == back["key"]

    out, home = await moved(both.headers)
    assert out["to_board"] is not None and out["new_key"] == away["key"]
    assert home["from_board"] is not None and home["old_key"] == away["key"]
