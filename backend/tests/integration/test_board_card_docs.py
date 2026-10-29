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

"""Card documents: every save is a version, and restoring makes a new one."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

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


async def _card(client: AsyncClient, factory: Factory) -> tuple[Person, Person, str]:
    org = await new_org(factory)
    admin = await person(factory, org, "pm")
    editor, viewer = [await person(factory, org) for _ in range(2)]
    key = (await make_board(client, admin))["board"]["key"]
    await put_role(client, admin, key, editor.id, "editor")
    card = await make_card(client, admin, key)
    return editor, viewer, f"{BOARDS}/{key}/cards/{card['number']}"


async def test_documents_keep_every_version_and_restore_as_a_new_one(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    editor, viewer, url = await _card(client, pg_session_factory)
    for text in ("v1", "v2"):
        ok(await client.put(f"{url}/docs/prd", json={"body_md": text}, headers=editor.headers))
    ok(await client.put(f"{url}/docs/notes", json={"body_md": "n"}, headers=editor.headers))
    current = ok(await client.get(f"{url}/docs", headers=viewer.headers))["items"]
    assert sorted((d["kind"], d["version"], d["body_md"]) for d in current) == [
        ("notes", 1, "n"),
        ("prd", 2, "v2"),
    ]
    restored = ok(await client.post(f"{url}/docs/prd/restore/1", headers=editor.headers))
    assert (restored["version"], restored["body_md"], restored["source"]) == (3, "v1", "revert")
    versions = ok(await client.get(f"{url}/docs/prd/versions", headers=viewer.headers))
    assert [(v["version"], v["state"]) for v in versions] == [
        (3, "current"),
        (2, "superseded"),
        (1, "superseded"),
    ]
    assert (
        await client.post(f"{url}/docs/prd/restore/9", headers=editor.headers)
    ).status_code == 404
    assert (
        await client.put(f"{url}/docs/prd", json={"body_md": "x"}, headers=viewer.headers)
    ).status_code == 403
    assert (
        await client.put(f"{url}/docs/spec", json={"body_md": "x"}, headers=editor.headers)
    ).status_code == 422
