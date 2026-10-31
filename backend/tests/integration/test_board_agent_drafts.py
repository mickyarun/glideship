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

"""Reviewing an agent's draft: accept (as written or edited), reject, and what changes.

A draft is never the current version. Accepting writes a new current
version, so it can be reverted from the history; the card's ``has_prd``
follows only accepted documents. Each review announces ``doc_updated``.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient

from app.services import event_bus
from tests.integration.board_agent_support import (
    AgentEnv,
    add_skill,
    agent,
    agent_env,
    ai_on,
    set_agents,
)
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    make_board,
    make_card,
    ok,
    person,
    put_role,
    stage_id,
)
from tests.integration.mcp_support import mcp_env
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration
__all__ = ["agent_env", "mcp_env"]


@dataclass(frozen=True)
class Drafted:
    admin: Person
    viewer: Person
    board_id: str
    url: str
    agent_id: str


async def _drafted(
    client: AsyncClient, factory: Factory, env: AgentEnv, text: str = "# PRD v1"
) -> Drafted:
    org = await new_org(factory)
    admin = await person(factory, org, "org_owner")
    viewer = await person(factory, org)
    board = await make_board(client, admin)
    key, stage = board["board"]["key"], stage_id(board, "To do")
    await put_role(client, admin, key, viewer.id, "viewer")
    skill = await add_skill(factory, org)
    (stored,) = await set_agents(client, admin, key, stage, [agent(skill, "manual")])
    await ai_on(client, admin, key)
    made = await make_card(client, admin, key, stage_id=stage)
    url = f"{BOARDS}/{key}/cards/{made['number']}"
    d = Drafted(admin, viewer, board["board"]["id"], url, stored["id"])
    await _draft(client, env, d, text)
    return d


async def _draft(client: AsyncClient, env: AgentEnv, d: Drafted, text: str) -> None:
    env.runner.reply(text)
    ok(await client.post(f"{d.url}/agents/{d.agent_id}/run", headers=d.admin.headers), 202)
    await env.jobs.run_all()


async def _docs(client: AsyncClient, d: Drafted) -> dict[str, Any]:
    return dict(ok(await client.get(f"{d.url}/docs", headers=d.admin.headers)))


def _review(d: Drafted, draft: dict[str, Any], verb: str) -> str:
    return f"{d.url}/docs/{draft['kind']}/drafts/{draft['id']}/{verb}"


async def test_accepting_makes_a_new_current_version_and_sets_has_prd(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    d = await _drafted(client, pg_session_factory, agent_env)
    (draft,) = (await _docs(client, d))["drafts"]
    assert ok(await client.get(d.url, headers=d.admin.headers))["has_prd"] is False
    queue = event_bus.subscribe(f"board:{d.board_id}")
    try:
        body = {"base_version": None}
        accepted = ok(
            await client.post(_review(d, draft, "accept"), json=body, headers=d.admin.headers)
        )
        await asyncio.sleep(0)
        events = [queue.get_nowait()["data"] for _ in range(queue.qsize())]
    finally:
        event_bus.unsubscribe(f"board:{d.board_id}", queue)
    assert (accepted["state"], accepted["version"], accepted["body_md"]) == (
        "current",
        2,
        "# PRD v1",
    )
    assert accepted["source"] == "agent"
    assert accepted["agent_run_id"] == draft["agent_run_id"]
    assert accepted["reviewed_by"] == str(d.admin.id)
    docs = await _docs(client, d)
    assert [i["version"] for i in docs["items"]] == [2]
    assert docs["drafts"] == []
    versions = ok(await client.get(f"{d.url}/docs/prd/versions", headers=d.admin.headers))
    assert [(v["version"], v["state"]) for v in versions["items"]] == [
        (2, "current"),
        (1, "superseded"),
    ]
    assert ok(await client.get(d.url, headers=d.admin.headers))["has_prd"] is True
    doc_events = [e for e in events if e["event"] == "doc_updated"]
    assert [e["state"] for e in doc_events] == ["current"]
    assert "card_updated" in [e["event"] for e in events]
    # Already reviewed: a second accept finds nothing waiting.
    again = await client.post(_review(d, draft, "accept"), json=body, headers=d.admin.headers)
    assert again.status_code == 404


async def test_accepting_an_edit_saves_the_edit_as_a_person_wrote_it(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    d = await _drafted(client, pg_session_factory, agent_env)
    (draft,) = (await _docs(client, d))["drafts"]
    body = {"base_version": None, "body_md": "# PRD, tightened"}
    accepted = ok(
        await client.post(_review(d, draft, "accept"), json=body, headers=d.admin.headers)
    )
    assert (accepted["body_md"], accepted["source"]) == ("# PRD, tightened", "ui")


async def test_accepting_over_a_newer_current_version_is_409(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    d = await _drafted(client, pg_session_factory, agent_env)
    (draft,) = (await _docs(client, d))["drafts"]
    write = {"body_md": "# Typed by hand", "base_version": None}
    ok(await client.put(f"{d.url}/docs/prd", json=write, headers=d.admin.headers))
    stale = await client.post(
        _review(d, draft, "accept"), json={"base_version": None}, headers=d.admin.headers
    )
    assert stale.status_code == 409
    fresh = await client.post(
        _review(d, draft, "accept"), json={"base_version": 2}, headers=d.admin.headers
    )
    assert ok(fresh)["version"] == 3


async def test_rejecting_keeps_the_card_and_marks_the_draft(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    d = await _drafted(client, pg_session_factory, agent_env)
    (draft,) = (await _docs(client, d))["drafts"]
    assert (
        await client.post(_review(d, draft, "reject"), headers=d.viewer.headers)
    ).status_code == 403
    rejected = ok(await client.post(_review(d, draft, "reject"), headers=d.admin.headers))
    assert (rejected["state"], rejected["reviewed_by"]) == ("rejected", str(d.admin.id))
    assert await _docs(client, d) == {"items": [], "drafts": []}
    assert ok(await client.get(d.url, headers=d.admin.headers))["has_prd"] is False


async def test_a_newer_draft_replaces_the_waiting_one(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    d = await _drafted(client, pg_session_factory, agent_env)
    await _draft(client, agent_env, d, "# PRD v2")
    (draft,) = (await _docs(client, d))["drafts"]
    assert (draft["body_md"], draft["version"]) == ("# PRD v2", 2)
    missing = f"{d.url}/docs/prd/drafts/{uuid.uuid4()}/accept"
    resp = await client.post(missing, json={"base_version": None}, headers=d.admin.headers)
    assert resp.status_code == 404
