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

"""What hangs off a card: checklist, comments and attachments."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services.boards import attachment_service
from app.services.file_storage import FileStorage
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    make_board,
    make_card,
    ok,
    person,
    put_role,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _local_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = FileStorage()
    storage.use_s3 = False
    storage.local_dir = str(tmp_path)
    monkeypatch.setattr(attachment_service, "get_file_storage", lambda: storage)


async def _card(client: AsyncClient, factory: Factory) -> tuple[Person, Person, Person, str]:
    """An admin, an editor and a viewer on a board, and the url of one card on it."""
    org = await new_org(factory)
    admin = await person(factory, org, "pm")
    editor, viewer = [await person(factory, org) for _ in range(2)]
    key = (await make_board(client, admin, visibility="members"))["board"]["key"]
    await put_role(client, admin, key, editor.id, "editor")
    await put_role(client, admin, key, viewer.id, "viewer")
    card = await make_card(client, admin, key)
    return admin, editor, viewer, f"{BOARDS}/{key}/cards/{card['number']}"


async def test_the_checklist_counts_on_the_card(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    _, editor, viewer, url = await _card(client, pg_session_factory)
    items = [
        ok(await client.post(f"{url}/checklist", json={"text": t}, headers=editor.headers), 201)
        for t in ("One", "Two", "Three")
    ]
    ok(
        await client.patch(
            f"{url}/checklist/{items[1]['id']}", json={"done": True}, headers=editor.headers
        )
    )
    card = ok(await client.get(url, headers=viewer.headers))
    assert (card["checklist_done"], card["checklist_total"]) == (1, 3)
    order = [items[2]["id"], items[0]["id"], items[1]["id"]]
    ok(
        await client.put(
            f"{url}/checklist/order", json={"item_ids": order}, headers=editor.headers
        )
    )
    listed = ok(await client.get(f"{url}/checklist", headers=viewer.headers))
    assert [i["text"] for i in listed] == ["Three", "One", "Two"]
    ok(await client.delete(f"{url}/checklist/{items[0]['id']}", headers=editor.headers), 204)
    assert ok(await client.get(url, headers=viewer.headers))["checklist_total"] == 2
    tick = await client.patch(
        f"{url}/checklist/{items[2]['id']}", json={"done": True}, headers=viewer.headers
    )
    assert tick.status_code == 403


async def test_comments_are_author_only_and_tombstoned(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    admin, editor, viewer, url = await _card(client, pg_session_factory)
    mine = ok(
        await client.post(f"{url}/comments", json={"body": "Hi"}, headers=viewer.headers), 201
    )
    assert mine["author_id"] == str(viewer.id)
    for who in (editor, admin):
        edit = await client.patch(
            f"{url}/comments/{mine['id']}", json={"body": "x"}, headers=who.headers
        )
        assert edit.status_code == 403
        assert (
            await client.delete(f"{url}/comments/{mine['id']}", headers=who.headers)
        ).status_code == 403
    edited = ok(
        await client.patch(
            f"{url}/comments/{mine['id']}", json={"body": "Hello"}, headers=viewer.headers
        )
    )
    assert edited["body"] == "Hello" and edited["edited_at"] is not None
    gone = ok(await client.delete(f"{url}/comments/{mine['id']}", headers=viewer.headers))
    assert gone["body"] == "" and gone["deleted_at"] is not None
    again = await client.patch(
        f"{url}/comments/{mine['id']}", json={"body": "x"}, headers=viewer.headers
    )
    assert again.status_code == 409
    thread = ok(await client.get(f"{url}/comments", headers=viewer.headers))
    assert [(c["id"], c["body"]) for c in thread] == [(mine["id"], "")]
    history = ok(await client.get(f"{url}/events", headers=viewer.headers))
    assert "commented" in [e["type"] for e in history["items"]]


async def test_a_comment_id_from_another_card_is_not_found(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    admin, _, _, url = await _card(client, pg_session_factory)
    key = url.split("/")[4]
    other = await make_card(client, admin, key, "Other")
    other_url = f"{BOARDS}/{key}/cards/{other['number']}"
    theirs = ok(
        await client.post(f"{other_url}/comments", json={"body": "x"}, headers=admin.headers), 201
    )
    for resp in (
        await client.patch(
            f"{url}/comments/{theirs['id']}", json={"body": "y"}, headers=admin.headers
        ),
        await client.delete(f"{url}/comments/{theirs['id']}", headers=admin.headers),
    ):
        assert resp.status_code == 404


def _file(name: str, data: bytes = b"\x89PNG data") -> dict[str, Any]:
    return {"file": (name, data, "application/octet-stream")}


async def test_files_and_links_with_their_limits(
    client: AsyncClient, pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin, editor, viewer, url = await _card(client, pg_session_factory)
    monkeypatch.setattr(settings.boards, "attachment_max_files", 2)
    uploaded = ok(
        await client.post(f"{url}/attachments", files=_file("shot.png"), headers=editor.headers),
        201,
    )
    assert (uploaded["kind"], uploaded["mime_type"]) == ("file", "image/png")
    link = {"url": "https://example.com/spec", "title": "Spec"}
    for _ in range(3):  # links don't count toward the cap
        ok(await client.post(f"{url}/attachments/links", json=link, headers=editor.headers), 201)
    ok(
        await client.post(f"{url}/attachments", files=_file("two.png"), headers=editor.headers),
        201,
    )
    full = await client.post(
        f"{url}/attachments", files=_file("three.png"), headers=editor.headers
    )
    assert full.status_code == 409
    listed = ok(await client.get(f"{url}/attachments", headers=viewer.headers))
    assert len(listed["items"]) == 5 and listed["limits"]["max_files"] == 2

    monkeypatch.setattr(settings.boards, "attachment_max_files", 10)
    wrong_type = await client.post(
        f"{url}/attachments", files=_file("run.exe"), headers=editor.headers
    )
    assert wrong_type.status_code == 422
    monkeypatch.setattr(settings.boards, "attachment_max_file_mb", 1)
    big = _file("big.png", b"x" * (1024 * 1024 + 1))
    assert (
        await client.post(f"{url}/attachments", files=big, headers=editor.headers)
    ).status_code == 413
    bad_link = await client.post(
        f"{url}/attachments/links", json={"url": "javascript:alert(1)"}, headers=editor.headers
    )
    assert bad_link.status_code == 422

    download = await client.get(f"{url}/attachments/{uploaded['id']}", headers=viewer.headers)
    assert download.status_code == 200 and download.content == b"\x89PNG data"
    assert download.headers["x-content-type-options"] == "nosniff"
    other_editor = await person(pg_session_factory, await _org(client, admin))
    await put_role(client, admin, url.split("/")[4], other_editor.id, "editor")
    not_theirs = await client.delete(
        f"{url}/attachments/{uploaded['id']}", headers=other_editor.headers
    )
    assert not_theirs.status_code == 403
    ok(await client.delete(f"{url}/attachments/{uploaded['id']}", headers=admin.headers), 204)
    assert (
        await client.get(f"{url}/attachments/{uploaded['id']}", headers=viewer.headers)
    ).status_code == 404


async def _org(client: AsyncClient, who: Person) -> uuid.UUID:
    return uuid.UUID(ok(await client.get("/api/v1/auth/me", headers=who.headers))["org_id"])
