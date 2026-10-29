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

"""A card's files and links: limits, download headers, other cards' ids and cleanup."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.config import settings
from app.repositories.board_card_thread import BoardCardAttachmentRepository
from app.services.attachment_upload import FILENAME_MAX
from tests.integration.board_api_support import (
    BOARDS,
    card_team,
    make_card,
    ok,
    person,
    put_role,
    use_local_storage,
)
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration

PNG = b"\x89PNG data"


@pytest.fixture(autouse=True)
def _storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_local_storage(tmp_path, monkeypatch)


def _file(name: str, data: bytes = PNG) -> dict[str, Any]:
    return {"file": (name, data, "application/octet-stream")}


async def test_files_and_links_have_their_own_caps(
    client: AsyncClient, pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    team = await card_team(client, pg_session_factory)
    url, editor = f"{team.url}/attachments", team.editor
    monkeypatch.setattr(settings.boards, "attachment_max_files", 2)
    first = ok(await client.post(url, files=_file("shot.png"), headers=editor.headers), 201)
    assert (first["kind"], first["mime_type"]) == ("file", "image/png")
    for _ in range(3):
        link = {"url": "https://example.com/spec", "title": "Spec"}
        ok(await client.post(f"{url}/links", json=link, headers=editor.headers), 201)
    ok(await client.post(url, files=_file("two.png"), headers=editor.headers), 201)
    assert (
        await client.post(url, files=_file("three.png"), headers=editor.headers)
    ).status_code == 409
    listed = ok(await client.get(url, headers=team.viewer.headers))
    assert len(listed["items"]) == 5 and listed["limits"]["max_files"] == 2

    monkeypatch.setattr(settings.boards, "attachment_max_files", 10)
    assert (
        await client.post(url, files=_file("run.exe"), headers=editor.headers)
    ).status_code == 422
    monkeypatch.setattr(settings.boards, "attachment_max_file_mb", 1)
    big = _file("big.png", b"x" * (1024 * 1024 + 1))
    assert (await client.post(url, files=big, headers=editor.headers)).status_code == 413
    bad = await client.post(
        f"{url}/links", json={"url": "javascript:alert(1)"}, headers=editor.headers
    )
    assert bad.status_code == 422


async def test_downloads_are_safe_attachments(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    team = await card_team(client, pg_session_factory)
    url = f"{team.url}/attachments"
    name = 'quo"te\r\nX-Evil: 1 ' + "y" * 600 + ".png"
    row = ok(await client.post(url, files=_file(name), headers=team.editor.headers), 201)
    assert len(row["filename"]) <= FILENAME_MAX and row["filename"].endswith(".png")
    download = await client.get(f"{url}/{row['id']}", headers=team.viewer.headers)
    assert download.status_code == 200 and download.content == PNG
    disposition = download.headers["content-disposition"]
    assert re.fullmatch(r'attachment; filename="[A-Za-z0-9._-]+"', disposition), disposition
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["content-security-policy"] == "default-src 'none'; sandbox"
    link = ok(
        await client.post(
            f"{url}/links", json={"url": "https://example.com"}, headers=team.editor.headers
        ),
        201,
    )
    assert (
        await client.get(f"{url}/{link['id']}", headers=team.viewer.headers)
    ).status_code == 404


async def test_removal_rules_and_other_cards_ids(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    team = await card_team(client, pg_session_factory)
    url = f"{team.url}/attachments"
    row = ok(await client.post(url, files=_file("a.png"), headers=team.editor.headers), 201)
    other = await make_card(client, team.admin, team.key, "Other")
    other_url = f"{BOARDS}/{team.key}/cards/{other['number']}/attachments/{row['id']}"
    assert (await client.get(other_url, headers=team.admin.headers)).status_code == 404
    assert (await client.delete(other_url, headers=team.admin.headers)).status_code == 404

    org = (await client.get("/api/v1/auth/me", headers=team.admin.headers)).json()["org_id"]
    colleague = await person(pg_session_factory, uuid.UUID(org))
    await put_role(client, team.admin, team.key, colleague.id, "editor")
    one = f"{url}/{row['id']}"
    assert (await client.delete(one, headers=colleague.headers)).status_code == 403
    ok(await client.post(f"{team.url}/archive", headers=team.editor.headers))
    assert (await client.delete(one, headers=team.admin.headers)).status_code == 409
    ok(await client.post(f"{team.url}/restore", headers=team.editor.headers))
    ok(await client.delete(one, headers=team.admin.headers), 204)
    assert (await client.get(one, headers=team.viewer.headers)).status_code == 404


async def test_a_failed_insert_removes_the_stored_file(
    client: AsyncClient,
    pg_session_factory: Factory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team = await card_team(client, pg_session_factory)

    async def _boom(self: object, row: object) -> object:
        raise RuntimeError("insert failed")

    monkeypatch.setattr(BoardCardAttachmentRepository, "create", _boom)
    with pytest.raises(RuntimeError):
        await client.post(
            f"{team.url}/attachments", files=_file("a.png"), headers=team.editor.headers
        )
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []
