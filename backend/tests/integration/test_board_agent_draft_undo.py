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

"""Undo after accepting an agent's draft: restoring the version it replaced.

The card page's Undo is the restore route: editors only, with the current
version it saw as ``base_version``, and the board hears ``doc_updated``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from httpx import AsyncClient

from app.services import event_bus
from tests.integration.board_agent_setup import agent_card, start
from tests.integration.board_agent_support import AgentEnv, agent_env
from tests.integration.board_api_support import ok, person, put_role
from tests.integration.mcp_support import mcp_env
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration
__all__ = ["agent_env", "mcp_env"]


async def test_restoring_right_after_accepting_brings_the_old_text_back(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    docs_url = f"{s.card_url}/docs"
    hand = {"body_md": "# Written by hand", "base_version": None}
    ok(await client.put(f"{docs_url}/prd", json=hand, headers=s.admin.headers))
    agent_env.runner.reply("# Written by the agent")
    await start(client, s)
    await agent_env.jobs.run_all()
    (draft,) = ok(await client.get(docs_url, headers=s.admin.headers))["drafts"]
    accept = f"{docs_url}/prd/drafts/{draft['id']}/accept"
    accepted = ok(await client.post(accept, json={"base_version": 1}, headers=s.admin.headers))
    assert accepted["version"] == 3

    restore = f"{docs_url}/prd/restore/1"
    viewer = await person(pg_session_factory, s.org)
    await put_role(client, s.admin, s.key, viewer.id, "viewer")
    seen = {"base_version": accepted["version"]}
    assert (await client.post(restore, json=seen, headers=viewer.headers)).status_code == 403
    assert (await client.post(restore, json={}, headers=s.assignee.headers)).status_code == 422
    stale = await client.post(restore, json={"base_version": 1}, headers=s.assignee.headers)
    assert stale.status_code == 409

    queue = event_bus.subscribe(f"board:{s.board_id}")
    try:
        undone = ok(await client.post(restore, json=seen, headers=s.assignee.headers))
        await asyncio.sleep(0)
        live: list[dict[str, Any]] = [queue.get_nowait()["data"] for _ in range(queue.qsize())]
    finally:
        event_bus.unsubscribe(f"board:{s.board_id}", queue)

    assert (undone["version"], undone["state"], undone["body_md"]) == (
        4,
        "current",
        "# Written by hand",
    )
    assert undone["source"] == "revert"
    (doc_event,) = [e for e in live if e["event"] == "doc_updated"]
    assert (doc_event["kind"], doc_event["version"], doc_event["state"]) == ("prd", 4, "current")
    (current,) = ok(await client.get(docs_url, headers=s.admin.headers))["items"]
    assert (current["version"], current["body_md"]) == (4, "# Written by hand")
