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

"""The positive half of the access matrix: viewers read everything, editors edit cards.

Each table must cover every route of its kind, so a new route needs a
row here as well as passing the 404/403/409 matrix.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.models.board_enums import BoardMemberRole
from tests.api.test_board_routes import ADMIN_READS, board_dep, board_routes
from tests.integration.board_api_support import (
    BOARDS,
    CardTeam,
    card_team,
    ok,
    stage_id,
    use_local_storage,
)
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration

CARD = f"{BOARDS}/{{key}}/cards/{{number}}"


@pytest.fixture(autouse=True)
def _storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_local_storage(tmp_path, monkeypatch)


async def _ids(client: AsyncClient, team: CardTeam) -> dict[str, str]:
    """Real ids for every path parameter, made by the board's admin."""
    admin = team.admin.headers
    board = ok(await client.get(f"{BOARDS}/{team.key}", headers=admin))
    item = ok(await client.post(f"{team.url}/checklist", json={"text": "x"}, headers=admin), 201)
    files = {"file": ("a.png", b"\x89PNG", "application/octet-stream")}
    attachment = ok(await client.post(f"{team.url}/attachments", files=files, headers=admin), 201)
    body = {"body_md": "v1", "base_version": None}
    ok(await client.put(f"{team.url}/docs/prd", json=body, headers=admin))
    card = ok(await client.get(team.url, headers=admin))
    return {
        "key": team.key,
        "number": str(card["number"]),
        "card_key": card["key"],
        "item_id": item["id"],
        "attachment_id": attachment["id"],
        "kind": "prd",
        "version": "1",
        "stage": stage_id(board, "To do"),
    }


def _url(path: str, ids: dict[str, str]) -> str:
    return path.format(**ids)


READS: dict[str, dict[str, str]] = {
    f"{BOARDS}": {},
    f"{BOARDS}/templates": {},
    f"{BOARDS}/limits": {},
    f"{BOARDS}/switcher": {},
    f"{BOARDS}/cards/by-key/{{card_key}}": {},
    f"{BOARDS}/{{key}}": {},
    f"{BOARDS}/{{key}}/members": {},
    f"{BOARDS}/{{key}}/labels": {},
    f"{BOARDS}/{{key}}/prefs": {},
    f"{BOARDS}/{{key}}/cards": {"stage_id": "{stage}"},
    CARD: {},
    f"{CARD}/checklist": {},
    f"{CARD}/events": {},
    f"{CARD}/comments": {},
    f"{CARD}/attachments": {},
    f"{CARD}/attachments/{{attachment_id}}": {},
    f"{CARD}/docs": {},
    f"{CARD}/docs/{{kind}}/versions": {},
    f"{CARD}/docs/{{kind}}/versions/{{version}}": {},
}

# In order: later rows rely on earlier ones (restore after archive, delete last).
EDITS: list[tuple[str, str, dict[str, Any]]] = [
    ("POST", f"{BOARDS}/{{key}}/cards", {"json": {"title": "New"}}),
    ("PATCH", CARD, {"json": {"title": "Edited"}}),
    ("POST", f"{CARD}/move", {"json": {"stage_id": "{stage}"}}),
    ("POST", f"{CARD}/checklist", {"json": {"text": "step"}}),
    ("PATCH", f"{CARD}/checklist/{{item_id}}", {"json": {"done": True}}),
    ("PUT", f"{CARD}/checklist/order", {"json": "ORDER"}),
    ("POST", f"{CARD}/attachments", {"files": {"file": ("b.png", b"\x89PNG", "x/y")}}),
    ("POST", f"{CARD}/attachments/links", {"json": {"url": "https://example.com"}}),
    ("PUT", f"{CARD}/docs/{{kind}}", {"json": {"body_md": "v2", "base_version": 1}}),
    ("POST", f"{CARD}/docs/{{kind}}/restore/{{version}}", {"json": {"base_version": 2}}),
    ("DELETE", f"{CARD}/checklist/{{item_id}}", {}),
    ("DELETE", f"{CARD}/attachments/{{attachment_id}}", {}),
    ("POST", f"{CARD}/archive", {}),
    ("POST", f"{CARD}/restore", {}),
]


def _fill(value: Any, ids: dict[str, str]) -> Any:
    if isinstance(value, str):
        return value.format(**ids)
    if isinstance(value, dict):
        return {k: _fill(v, ids) for k, v in value.items()}
    return value


def test_the_tables_cover_every_read_and_every_editor_route() -> None:
    reads = {r.path for r in board_routes() if r.methods == {"GET"}}
    assert reads == set(READS) | set(ADMIN_READS)
    editor_routes = {
        (next(iter(r.methods)), r.path)
        for r in board_routes()
        if r.methods != {"GET"}
        and board_dep(r) is not None
        and board_dep(r).board_min_role is BoardMemberRole.EDITOR
    }
    assert editor_routes == {(m, p) for m, p, _ in EDITS}


async def test_viewers_read_and_editors_edit(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    team = await card_team(client, pg_session_factory)
    ids = await _ids(client, team)
    for path, params in READS.items():
        resp = await client.get(
            _url(path, ids), params=_fill(params, ids), headers=team.viewer.headers
        )
        assert resp.status_code == 200, (path, resp.text)

    # The editor uploads the attachment it later removes; uploaders may.
    files = {"file": ("mine.png", b"\x89PNG", "x/y")}
    mine = ok(
        await client.post(f"{team.url}/attachments", files=files, headers=team.editor.headers), 201
    )
    ids["attachment_id"] = mine["id"]
    for method, path, kwargs in EDITS:
        args = _fill(kwargs, ids)
        if args.get("json") == "ORDER":
            items = ok(await client.get(f"{team.url}/checklist", headers=team.editor.headers))
            args["json"] = {"item_ids": [i["id"] for i in items]}
        resp = await client.request(method, _url(path, ids), headers=team.editor.headers, **args)
        assert 200 <= resp.status_code < 300, (method, path, resp.text)
