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

"""Card documents: every save is a version, saves are optimistic, restoring makes a new one."""

from __future__ import annotations

from typing import Any

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


async def _save(
    client: AsyncClient, who: Person, url: str, kind: str, text: str, base: int | None
) -> dict[str, Any]:
    body = {"body_md": text, "base_version": base}
    return ok(await client.put(f"{url}/docs/{kind}", json=body, headers=who.headers))


async def test_documents_keep_every_version_and_restore_as_a_new_one(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    editor, viewer, url = await _card(client, pg_session_factory)
    await _save(client, editor, url, "prd", "v1", None)
    await _save(client, editor, url, "prd", "v2", 1)
    await _save(client, editor, url, "notes", "n", None)
    current = ok(await client.get(f"{url}/docs", headers=viewer.headers))["items"]
    assert sorted((d["kind"], d["version"], d["body_md"]) for d in current) == [
        ("notes", 1, "n"),
        ("prd", 2, "v2"),
    ]
    restore = f"{url}/docs/prd/restore/1"
    restored = ok(await client.post(restore, json={"base_version": 2}, headers=editor.headers))
    assert (restored["version"], restored["body_md"], restored["source"]) == (3, "v1", "revert")

    versions = ok(await client.get(f"{url}/docs/prd/versions", headers=viewer.headers))
    assert [(v["version"], v["state"]) for v in versions["items"]] == [
        (3, "current"),
        (2, "superseded"),
        (1, "superseded"),
    ]
    assert all("body_md" not in v for v in versions["items"])
    one = ok(await client.get(f"{url}/docs/prd/versions/2", headers=viewer.headers))
    assert one["body_md"] == "v2"
    first = ok(
        await client.get(f"{url}/docs/prd/versions", params={"limit": 2}, headers=viewer.headers)
    )
    rest = ok(
        await client.get(
            f"{url}/docs/prd/versions",
            params={"limit": 2, "before": first["next_before"]},
            headers=viewer.headers,
        )
    )
    assert [v["version"] for v in first["items"] + rest["items"]] == [3, 2, 1]
    assert rest["next_before"] is None


async def test_a_save_from_a_stale_version_is_refused(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    editor, viewer, url = await _card(client, pg_session_factory)
    await _save(client, editor, url, "prd", "v1", None)
    for base in (None, 7):
        body = {"body_md": "late", "base_version": base}
        assert (
            await client.put(f"{url}/docs/prd", json=body, headers=editor.headers)
        ).status_code == 409
    stale = await client.post(
        f"{url}/docs/prd/restore/1", json={"base_version": None}, headers=editor.headers
    )
    assert stale.status_code == 409
    missing = await client.post(
        f"{url}/docs/prd/restore/9", json={"base_version": 1}, headers=editor.headers
    )
    assert missing.status_code == 404
    as_viewer = await client.put(
        f"{url}/docs/prd", json={"body_md": "x", "base_version": 1}, headers=viewer.headers
    )
    assert as_viewer.status_code == 403
    wrong_kind = await client.put(
        f"{url}/docs/spec", json={"body_md": "x", "base_version": None}, headers=editor.headers
    )
    assert wrong_kind.status_code == 422
    unversioned = await client.put(
        f"{url}/docs/prd", json={"body_md": "x"}, headers=editor.headers
    )
    assert unversioned.status_code == 422
