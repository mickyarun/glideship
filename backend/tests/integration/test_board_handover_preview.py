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

"""What a handover carries: the preview, the repositories, similar BUDs, the owner's notice."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models.board_handover import BoardCardHandover
from app.models.bud import BUDDocument, BUDStatus, BUDTimelineEvent
from app.models.notification import Notification
from app.models.tracked_repository import RepoStatus, TrackedRepository
from tests.integration.board_api_support import link_repo, ok, tracked_repo
from tests.integration.board_handover_support import card, desk, hand_over, preview, stubbed
from tests.integration.board_notify_support import Slack, fake_slack, link_slack, notes
from tests.integration.bud_lifecycle_reads import count_rows, load_bud
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.scan_features_bugs_support import Factory, new_bud, vec

pytestmark = pytest.mark.integration

FIGMA = "https://www.figma.com/design/AbC123/Pricing"


@pytest.fixture
def slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> Slack:
    return fake_slack(monkeypatch, pg_session_factory)


async def _counts(factory: Factory, org: uuid.UUID) -> list[int]:
    models = (BUDDocument, BoardCardHandover, BUDTimelineEvent, Notification)
    return [await count_rows(factory, model, org) for model in models]


async def test_preview_builds_the_draft_and_writes_nothing(
    client: AsyncClient, pg_session_factory: Factory, slack: Slack
) -> None:
    """PRD first, then the board's checklist, links, brief and a link back; P2 by default."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, "Pricing page", description_md="Old description")
    h = d.pm.headers
    ok(
        await client.put(
            f"{url}/docs/prd", json={"body_md": "The PRD", "base_version": None}, headers=h
        )
    )
    brief = {"body_md": "Calm, two columns", "base_version": None}
    ok(await client.put(f"{url}/docs/design_brief", json=brief, headers=h))
    ok(await client.post(f"{url}/checklist", json={"text": "Copy"}, headers=h), 201)
    for link in ({"url": "https://example.com/spec", "title": "Spec"}, {"url": FIGMA}):
        ok(await client.post(f"{url}/attachments/links", json=link, headers=h), 201)
    before = await _counts(pg_session_factory, d.org)

    with stubbed():
        shown = ok(await preview(client, d.pm, url))

    assert await _counts(pg_session_factory, d.org) == before
    assert (shown["title"], shown["priority"], shown["figma_url"]) == ("Pricing page", "P2", FIGMA)
    assert (shown["mode"], shown["target_status"]) == ("create", "bud")
    body = shown["requirements_md"]
    assert body.startswith("The PRD\n\n## From the board")
    assert "- [ ] Copy" in body and "[Spec](<https://example.com/spec>)" in body
    assert "Calm, two columns" in body and f"/boards/{d.key}/cards/" in body
    assert "Old description" not in body
    assert "CHECKLIST_OPEN" in [w["code"] for w in shown["warnings"]]


async def test_repositories_come_from_the_card_else_the_board(
    client: AsyncClient, pg_session_factory: Factory, slack: Slack
) -> None:
    """The card's repo alone; otherwise every active repo the board links."""
    d = await desk(client, pg_session_factory)
    one, two, retired = [await tracked_repo(pg_session_factory, d.org) for _ in range(3)]
    for repo in (one, two, retired):
        await link_repo(client, d.pm, d.key, repo)
    async with pg_session_factory() as db:
        await db.execute(
            update(TrackedRepository)
            .where(TrackedRepository.id == retired)
            .values(status=RepoStatus.IGNORED)
        )
        await db.commit()
    with_repo = await card(client, d, repo_id=str(two))
    plain = await card(client, d)
    with stubbed():
        own = ok(await preview(client, d.pm, with_repo))
        board = ok(await preview(client, d.pm, plain))
        made = ok(await hand_over(client, d.pm, plain), 201)

    assert [r["repo_id"] for r in own["impacted_repos"]] == [str(two)]
    assert {r["repo_id"] for r in board["impacted_repos"]} == {str(one), str(two)}
    bud = await load_bud(pg_session_factory, uuid.UUID(made["handover"]["bud_id"]))
    assert {r["repo_id"] for r in bud.impacted_repos or []} == {str(one), str(two)}


async def test_similar_open_buds_nearest_first_under_the_threshold(
    client: AsyncClient, pg_session_factory: Factory, slack: Slack
) -> None:
    """Closed and distant BUDs are left out; the warning names it."""
    d = await desk(client, pg_session_factory)
    near = await new_bud(
        pg_session_factory, d.org, 1, status=BUDStatus.DESIGN, embedding=vec(10, 1)
    )
    same = await new_bud(pg_session_factory, d.org, 2, status=BUDStatus.BUD, embedding=vec(1))
    await new_bud(pg_session_factory, d.org, 3, status=BUDStatus.CLOSED, embedding=vec(1))
    await new_bud(pg_session_factory, d.org, 4, status=BUDStatus.BUD, embedding=vec(0, 1))
    url = await card(client, d, description_md="x")
    with stubbed(vec(1)):
        shown = ok(await preview(client, d.pm, url))
    assert [(s["bud_id"], s["key"]) for s in shown["similar"]] == [
        (str(same), "BUD-002"),
        (str(near), "BUD-001"),
    ]
    assert "SIMILAR_BUDS" in [w["code"] for w in shown["warnings"]]


async def test_the_owner_hears_by_dm_and_in_app(
    client: AsyncClient, pg_session_factory: Factory, slack: Slack
) -> None:
    """The designer assigned at design gets "SEO-14 was handed over as BUD-001"."""
    d = await desk(client, pg_session_factory)
    ids = await link_slack(pg_session_factory, d.org, d.designer.id, d.pm.id)
    url = await card(client, d, description_md="x")
    with stubbed():
        made = ok(await hand_over(client, d.pm, url, target_status="design"), 201)
    await slack.flush()

    key, bud_key = made["card"]["key"], made["handover"]["bud_key"]
    [text] = slack.to(ids[d.designer.id])
    assert f"{key} was handed over as" in text and f"*{bud_key}*" in text
    assert slack.to(ids[d.pm.id]) == []
    [note] = await notes(pg_session_factory, d.designer.id)
    assert (note.type.value, note.deep_link) == ("board_handover", "/buds/1")
