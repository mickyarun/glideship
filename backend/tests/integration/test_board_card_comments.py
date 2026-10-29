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

"""A card's comments: author-only changes, tombstones, paging and archived cards."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.board_api_support import BOARDS, card_team, make_card, ok
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration


async def test_comments_are_author_only_and_tombstoned(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    team = await card_team(client, pg_session_factory)
    url, viewer = f"{team.url}/comments", team.viewer
    mine = ok(await client.post(url, json={"body": " Hi "}, headers=viewer.headers), 201)
    assert (mine["author_id"], mine["body"]) == (str(viewer.id), "Hi")
    one = f"{url}/{mine['id']}"
    for who in (team.editor, team.admin):
        assert (
            await client.patch(one, json={"body": "x"}, headers=who.headers)
        ).status_code == 403
        assert (await client.delete(one, headers=who.headers)).status_code == 403
    edited = ok(await client.patch(one, json={"body": "Hello"}, headers=viewer.headers))
    assert edited["body"] == "Hello" and edited["edited_at"] is not None
    gone = ok(await client.delete(one, headers=viewer.headers))
    assert gone["body"] == "" and gone["deleted_at"] is not None
    assert (await client.patch(one, json={"body": "x"}, headers=viewer.headers)).status_code == 409
    thread = ok(await client.get(url, headers=viewer.headers))
    assert [(c["id"], c["body"]) for c in thread["items"]] == [(mine["id"], "")]
    blank = await client.post(url, json={"body": "   "}, headers=viewer.headers)
    assert blank.status_code == 422
    history = ok(await client.get(f"{team.url}/events", headers=viewer.headers))
    assert "commented" in [e["type"] for e in history["items"]]


async def test_comments_page_oldest_first(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    team = await card_team(client, pg_session_factory)
    url = f"{team.url}/comments"
    posted = [
        ok(await client.post(url, json={"body": f"c{i}"}, headers=team.viewer.headers), 201)
        for i in range(5)
    ]
    seen, cursor = [], None
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        body = ok(await client.get(url, params=params, headers=team.viewer.headers))
        seen += [c["id"] for c in body["items"]]
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert seen == [c["id"] for c in posted]


async def test_an_archived_cards_thread_is_read_only(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    team = await card_team(client, pg_session_factory)
    url, viewer = f"{team.url}/comments", team.viewer
    mine = ok(await client.post(url, json={"body": "Hi"}, headers=viewer.headers), 201)
    ok(await client.post(f"{team.url}/archive", headers=team.editor.headers))
    one = f"{url}/{mine['id']}"
    for resp in (
        await client.post(url, json={"body": "x"}, headers=viewer.headers),
        await client.patch(one, json={"body": "x"}, headers=viewer.headers),
        await client.delete(one, headers=viewer.headers),
    ):
        assert resp.status_code == 409
    assert len(ok(await client.get(url, headers=viewer.headers))["items"]) == 1


async def test_a_comment_id_from_another_card_is_not_found(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    team = await card_team(client, pg_session_factory)
    other = await make_card(client, team.admin, team.key, "Other")
    other_url = f"{BOARDS}/{team.key}/cards/{other['number']}/comments"
    theirs = ok(await client.post(other_url, json={"body": "x"}, headers=team.admin.headers), 201)
    one = f"{team.url}/comments/{theirs['id']}"
    edit = await client.patch(one, json={"body": "y"}, headers=team.admin.headers)
    gone = await client.delete(one, headers=team.admin.headers)
    assert (edit.status_code, gone.status_code) == (404, 404)
