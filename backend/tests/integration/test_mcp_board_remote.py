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


"""Board reads over the remote endpoint, and a BUD's origin card in ``get_bud_by_id``."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.mcp.streamable import _METHOD_NOT_FOUND
from tests.integration.board_api_support import BOARDS, ok
from tests.integration.board_handover_return_support import bud_of, handed
from tests.integration.board_handover_support import card, desk
from tests.integration.board_mcp_support import Tokened, board_desk, remote_result, tokened
from tests.integration.mcp_seed import mint_token, set_org_token
from tests.integration.mcp_support import (
    Factory,
    call,
    mcp_env,  # noqa: F401
    rpc,
)

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("mcp_env")]

READS = {"list_boards", "get_board", "get_card"}
WRITES = {"create_card", "update_card", "move_card", "comment_card", "write_card_doc"}


async def test_only_the_three_reads_are_remote(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    d = await board_desk(client, pg_session_factory)

    listed = await client.post(
        "/mcp/sse",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={"Authorization": f"Bearer {d.pm.token}"},
    )
    names = {t["name"] for t in listed.json()["result"]["tools"]}
    assert names >= READS and not names & WRITES
    is_error, out = remote_result(
        await rpc(client, d.pm.token, "get_card", {"card_key": d.card["key"]})
    )
    assert is_error is False and out["card"]["key"] == d.card["key"]
    is_error, out = remote_result(await rpc(client, d.pm.token, "get_board", {"board_key": d.key}))
    assert is_error is False and out["board"]["key"] == d.key
    # A refusal is an error result, with the API's status.
    is_error, out = remote_result(
        await rpc(client, d.outsider.token, "get_board", {"board_key": d.key})
    )
    assert is_error is True and out["status"] == 404
    for name in WRITES:
        resp = await rpc(client, d.pm.token, name, {"card_key": d.card["key"]})
        assert resp.json()["error"]["code"] == _METHOD_NOT_FOUND, name


async def test_an_org_token_gets_no_board_tools(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    d = await board_desk(client, pg_session_factory, visibility="org")
    org_token = await set_org_token(pg_session_factory, d.org)

    resp = await call(client, org_token, "list_boards")
    assert resp.status_code == 200 and resp.json()["status"] == 403


async def test_get_bud_by_id_names_the_origin_card_to_people_who_see_its_board(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    d = await desk(client, pg_session_factory)
    url = await card(client, d, "Pricing page")
    bud = bud_of(await handed(client, d.pm, url))
    ok(
        await client.patch(
            f"{BOARDS}/{d.key}", json={"visibility": "members"}, headers=d.pm.headers
        )
    )
    pm_token, _ = await mint_token(pg_session_factory, d.org, d.pm.id)
    pm = Tokened(d.pm, pm_token)
    outsider = await tokened(pg_session_factory, d.org)
    org_token = await set_org_token(pg_session_factory, d.org)

    async def origin(token: str) -> object:
        resp = await call(client, token, "get_bud_by_id", {"bud_id": str(bud)})
        assert resp.status_code == 200, resp.text
        return resp.json()["origin_card"]

    assert await origin(pm.token) == {
        "card_key": f"{d.key}-1",
        "board_key": d.key,
        "board_name": d.board["board"]["name"],
        "title": "Pricing page",
        "archived": False,
    }
    assert await origin(outsider.token) is None
    assert await origin(org_token) is None
