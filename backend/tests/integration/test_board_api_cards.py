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

"""Cards through the API: create, read, edit, assignees, labels, archive, and paging."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from tests.integration.board_api_support import (
    BOARDS,
    Person,
    make_board,
    make_card,
    ok,
    page,
    person,
    put_role,
    stage_id,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def _setup(client: AsyncClient, factory: Factory) -> tuple[Person, dict[str, Any], str]:
    """A pm in a new org and an org-visible ops board they admin."""
    org = await new_org(factory)
    pm = await person(factory, org, "pm")
    board = await make_board(client, pm, template="ops")
    return pm, board, board["board"]["key"]


async def _org_of(client: AsyncClient, who: Person) -> uuid.UUID:
    return uuid.UUID(ok(await client.get("/api/v1/auth/me", headers=who.headers))["org_id"])


async def test_cards_are_numbered_and_land_at_the_bottom_of_the_default_stage(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board, key = await _setup(client, pg_session_factory)
    first = await make_card(client, pm, key, "First", priority="P1")
    second = await make_card(client, pm, key, "Second")
    assert (first["key"], second["key"]) == (f"{key}-1", f"{key}-2")
    assert first["stage_id"] == second["stage_id"] == stage_id(board, "Backlog")
    assert first["position"] < second["position"]
    got = ok(await client.get(f"{BOARDS}/{key}/cards/1", headers=pm.headers))
    assert (got["title"], got["priority"], got["board_key"]) == ("First", "P1", key)
    assert (await client.get(f"{BOARDS}/{key}/cards/99", headers=pm.headers)).status_code == 404
    elsewhere = await make_card(client, pm, key, "Doing", stage_id=stage_id(board, "In progress"))
    assert elsewhere["started_at"] is not None and elsewhere["completed_at"] is None


async def test_editing_fields_assignees_and_labels(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, _, key = await _setup(client, pg_session_factory)
    org_dev = (await person(pg_session_factory, await _org_of(client, pm))).id
    label = ok(
        await client.post(
            f"{BOARDS}/{key}/labels", json={"name": "Urgent", "color": "red"}, headers=pm.headers
        ),
        201,
    )
    card = await make_card(client, pm, key)
    url = f"{BOARDS}/{key}/cards/{card['number']}"
    edits = {
        "title": "  Renamed ",
        "description_md": "Body",
        "due_at": "2026-12-01T09:00:00Z",
        "assignee_ids": [str(org_dev)],
        "label_ids": [label["id"]],
    }
    body = ok(await client.patch(url, json=edits, headers=pm.headers))
    assert (body["title"], body["description_md"]) == ("Renamed", "Body")
    assert body["assignee_ids"] == [str(org_dev)] and body["label_ids"] == [label["id"]]
    cleared = ok(
        await client.patch(url, json={"due_at": None, "label_ids": []}, headers=pm.headers)
    )
    assert cleared["due_at"] is None and cleared["label_ids"] == []
    for bad in (
        {"title": None},
        {"start_at": "2026-12-02T00:00:00Z", "due_at": "2026-12-01T00:00:00Z"},
    ):
        assert (await client.patch(url, json=bad, headers=pm.headers)).status_code == 422


async def test_assignees_need_board_access_and_labels_must_be_this_boards(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, other = await new_org(pg_session_factory), await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    board = await make_board(client, pm, visibility="members")
    key = board["board"]["key"]
    outsider = await person(pg_session_factory, org)
    foreigner = await person(pg_session_factory, other)
    other_board = await make_board(client, pm)
    their_label = ok(
        await client.post(
            f"{BOARDS}/{other_board['board']['key']}/labels",
            json={"name": "Theirs", "color": "blue"},
            headers=pm.headers,
        ),
        201,
    )
    url = f"{BOARDS}/{key}/cards"
    for bad in (
        {"assignee_ids": [str(outsider.id)]},
        {"assignee_ids": [str(foreigner.id)]},
        {"label_ids": [their_label["id"]]},
        {"label_ids": [str(uuid.uuid4())]},
    ):
        resp = await client.post(url, json={"title": "x", **bad}, headers=pm.headers)
        assert resp.status_code == 422, bad
    card = await make_card(client, pm, key)
    card_url = f"{url}/{card['number']}"
    for bad in ({"assignee_ids": [str(outsider.id)]}, {"label_ids": [their_label["id"]]}):
        assert (await client.patch(card_url, json=bad, headers=pm.headers)).status_code == 422
    await put_role(client, pm, key, outsider.id, "viewer")
    card = await make_card(client, pm, key, assignee_ids=[str(outsider.id)])
    assert card["assignee_ids"] == [str(outsider.id)]


async def test_archived_cards_leave_the_column_and_come_back_at_the_bottom(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board, key = await _setup(client, pg_session_factory)
    backlog = stage_id(board, "Backlog")
    first, _ = [await make_card(client, pm, key, t) for t in ("A", "B")]
    url = f"{BOARDS}/{key}/cards/{first['number']}"
    archived = ok(await client.post(f"{url}/archive", headers=pm.headers))
    assert archived["archived_at"] is not None
    assert [c["title"] for c in (await page(client, pm, key, backlog))["items"]] == ["B"]
    shelf = await page(client, pm, key, backlog, archived="true")
    assert [c["title"] for c in shelf["items"]] == ["A"]
    assert (await client.patch(url, json={"title": "x"}, headers=pm.headers)).status_code == 409
    ok(await client.post(f"{url}/restore", headers=pm.headers))
    assert [c["title"] for c in (await page(client, pm, key, backlog))["items"]] == ["B", "A"]


async def test_blank_titles_and_out_of_range_numbers_are_refused_cleanly(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board, key = await _setup(client, pg_session_factory)
    blank = await client.post(f"{BOARDS}/{key}/cards", json={"title": "   "}, headers=pm.headers)
    assert blank.status_code == 422
    huge = 2**31
    assert (
        await client.get(f"{BOARDS}/{key}/cards/{huge}", headers=pm.headers)
    ).status_code == 422
    by_key = await client.get(f"{BOARDS}/cards/by-key/{key}-{huge}", headers=pm.headers)
    assert by_key.status_code == 404
    found = await page(client, pm, key, stage_id(board, "Backlog"), q=str(huge))
    assert found["items"] == []
