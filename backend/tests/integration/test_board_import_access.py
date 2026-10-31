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

"""Who may import where, which sessions they can see, and what uploads are refused."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.config import settings
from app.models.user import User
from tests.integration.board_api_support import make_board, ok, person, put_role
from tests.integration.board_import_support import (
    IMPORTS,
    Jobs,
    capture_jobs,
    mapping,
    named,
    new_board,
    parsed,
    upload,
    use_import_storage,
)
from tests.integration.board_support import board_key
from tests.integration.scan_features_bugs_support import Factory, new_org
from tests.services.trello_fixture import BACKLOG, DOING, DONE, OLD, fixture_bytes

pytestmark = pytest.mark.integration


@pytest.fixture
def jobs(pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Jobs:
    use_import_storage(tmp_path, monkeypatch)
    return capture_jobs(pg_session_factory, monkeypatch)


def _existing(key: str) -> dict[str, object]:
    lists = [
        {"list_id": list_id, "action": "new", "name": f"Trello {n}", "category": category}
        for n, (list_id, category) in enumerate(
            [(BACKLOG, "todo"), (DOING, "in_progress"), (DONE, "done")]
        )
    ]
    return mapping(
        {"kind": "existing", "key": key}, lists=[*lists, {"list_id": OLD, "action": "skip"}]
    )


async def test_who_may_import_into_which_board(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    dev = await person(pg_session_factory, org, "developer")
    # No boards:create and admin nowhere: can't even upload.
    assert (await upload(client, dev)).status_code == 403

    open_board = await make_board(client, pm)
    hidden = await make_board(client, pm, visibility="members")
    await put_role(client, pm, open_board["board"]["key"], dev.id, "admin")
    # Admin on one board is enough to upload, and to import into that board only.
    session = await parsed(client, dev, jobs)
    url = f"{IMPORTS}/{session}/mapping"
    put = client.put
    assert (
        await put(url, json=mapping(new_board(board_key())), headers=dev.headers)
    ).status_code == 403
    assert (
        await put(url, json=_existing(hidden["board"]["key"]), headers=dev.headers)
    ).status_code == 404
    editor_board = await make_board(client, pm)
    await put_role(client, pm, editor_board["board"]["key"], dev.id, "editor")
    assert (
        await put(url, json=_existing(editor_board["board"]["key"]), headers=dev.headers)
    ).status_code == 403
    ok(await put(url, json=_existing(open_board["board"]["key"]), headers=dev.headers))

    # The session is the uploader's: a colleague and another org get 404.
    other_org = await new_org(pg_session_factory)
    outsider = await person(pg_session_factory, other_org, "pm")
    for who in (pm, outsider):
        assert (await client.get(f"{IMPORTS}/{session}", headers=who.headers)).status_code == 404
        start = await client.post(f"{IMPORTS}/{session}/start", headers=who.headers)
        assert start.status_code == 404
    admin = await person(pg_session_factory, org, "admin")  # boards:manage sees every session
    ok(await client.get(f"{IMPORTS}/{session}", headers=admin.headers))


async def test_the_mapping_is_checked_against_the_board_and_the_people(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    gone = await named(pg_session_factory, org, "Priya Sharma")
    async with pg_session_factory() as db:
        await db.execute(update(User).where(User.id == gone.id).values(is_active=False))
        await db.commit()
    session = await parsed(client, pm, jobs)
    url = f"{IMPORTS}/{session}/mapping"

    async def status_of(body: dict[str, object]) -> int:
        return (await client.put(url, json=body, headers=pm.headers)).status_code

    key = board_key()
    lists = [{"list_id": BACKLOG, "action": "new", "name": "Backlog", "category": "todo"}]
    assert await status_of(mapping(new_board(key), lists=lists)) == 422  # not every list
    two_categories = [
        {"list_id": BACKLOG, "action": "new", "name": "Work", "category": "todo"},
        {"list_id": DOING, "action": "new", "name": "work", "category": "in_progress"},
        {"list_id": DONE, "action": "new", "name": "Done", "category": "done"},
    ]
    body = mapping(new_board(key))
    body["lists"] = [*two_categories, body["lists"][-1]]
    assert await status_of(body) == 422
    assert await status_of(mapping(new_board("BUD"))) == 422  # reserved key
    taken = await make_board(client, pm)
    assert await status_of(mapping(new_board(taken["board"]["key"]))) == 409
    # Someone who can't open boards (here, deactivated) can't be mapped.
    assert await status_of(mapping(new_board(key), priya=gone.id)) == 422
    unknown = mapping(new_board(key))
    unknown["members"] = [{"member_id": "f" * 24, "user_id": None}]
    assert await status_of(unknown) == 422
    saved = ok(await client.put(url, json=mapping(new_board(key.lower())), headers=pm.headers))
    assert saved["mapping"]["target"]["key"] == key


async def test_uploads_are_capped_and_must_be_a_board_export(
    client: AsyncClient,
    pg_session_factory: Factory,
    jobs: Jobs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    assert (await upload(client, pm, name="board.csv")).status_code == 422
    assert (await upload(client, pm, data=b"{not json")).status_code == 422
    assert (await upload(client, pm, data=b'{"hello": "world"}')).status_code == 422
    monkeypatch.setattr(settings.boards, "import_max_upload_bytes", len(fixture_bytes()) - 1)
    assert (await upload(client, pm)).status_code == 413
    assert jobs.queued == []
    no_file = await client.post(IMPORTS, files={"other": ("a.json", b"{}")}, headers=pm.headers)
    assert no_file.status_code == 422
    # API mode needs the org's Trello credentials.
    api = await client.post(
        IMPORTS, json={"mode": "api", "trello_board_id": "AbCdEf12"}, headers=pm.headers
    )
    assert api.status_code == 422 and "Trello isn't connected" in api.text
    bad = await client.post(
        IMPORTS, json={"mode": "api", "trello_board_id": "../x"}, headers=pm.headers
    )
    assert bad.status_code == 422
