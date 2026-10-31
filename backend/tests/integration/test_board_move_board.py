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

"""Moving a card to another board: new key, old key kept, what it keeps, and live events."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.integration.board_api_support import (
    BOARDS,
    link_repo,
    make_board,
    make_card,
    ok,
    org_of,
    person,
    put_role,
    stage_id,
    tracked_repo,
)
from tests.integration.board_move_board_support import heard, label, move_board, two_boards
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration
BY_KEY = f"{BOARDS}/cards/by-key"


async def test_a_card_moves_with_a_new_key_and_its_old_key_still_opens_it(
    client: AsyncClient, pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    two = await two_boards(client, pg_session_factory)
    pm, src, dst = two.pm, two.src, two.dst
    org = await org_of(pg_session_factory, pm)
    stays, leaves = [await person(pg_session_factory, org) for _ in range(2)]
    for who, role in ((stays, "editor"), (leaves, "viewer")):
        await put_role(client, pm, src, who.id, "editor")
        await put_role(client, pm, dst, who.id, role)
    kept_repo, lost_repo = [await tracked_repo(pg_session_factory, org) for _ in range(2)]
    for repo in (kept_repo, lost_repo):
        await link_repo(client, pm, src, repo)
    await link_repo(client, pm, dst, kept_repo)
    labels = [await label(client, pm, src, name) for name in ("Bug", "Docs")]
    target_bug = await label(client, pm, dst, "bug")
    await make_card(client, pm, dst, "Already there")
    card = await make_card(
        client,
        pm,
        src,
        "Wandering",
        stage_id=stage_id(two.source, "Waiting"),
        label_ids=labels,
        assignee_ids=[str(stays.id), str(leaves.id)],
        repo_id=str(kept_repo),
    )
    other = await make_card(client, pm, src, "Repo goes", repo_id=str(lost_repo))
    sent = heard(monkeypatch)

    moved = ok(await move_board(client, pm, src, card, dst.lower()))
    assert (moved["key"], moved["board_key"], moved["number"]) == (f"{dst}-2", dst, 2)
    # Waiting is in progress; the blank board's first in-progress stage takes it.
    assert moved["stage_id"] == stage_id(two.target, "In progress")
    assert moved["label_ids"] == [target_bug]
    assert moved["assignee_ids"] == [str(stays.id)]
    assert moved["repo_id"] == str(kept_repo)
    assert moved["id"] == card["id"]

    found = ok(await client.get(f"{BY_KEY}/{card['key']}", headers=pm.headers))
    assert (found["id"], found["key"]) == (card["id"], moved["key"])
    gone = await client.get(f"{BOARDS}/{src}/cards/{card['number']}", headers=pm.headers)
    assert gone.status_code == 404

    events = [(topic, data["event"], data) for topic, data in sent]
    source_id, target_id = two.source["board"]["id"], two.target["board"]["id"]
    (left,) = [d for t, e, d in events if e == "card_left_board"]
    assert (left["card_id"], left["new_key"], left["to_board_key"]) == (
        card["id"],
        moved["key"],
        dst,
    )
    assert [t for t, e, _ in events if e == "card_left_board"] == [f"board:{source_id}"]
    (arrived,) = [(t, d) for t, e, d in events if e == "card_created"]
    assert arrived[0] == f"board:{target_id}" and arrived[1]["card"]["key"] == moved["key"]

    history = ok(await client.get(f"{BOARDS}/{dst}/cards/2/events", headers=pm.headers))
    entry = next(e for e in history["items"] if e["type"] == "moved_board")
    detail: dict[str, Any] = entry["detail"]
    assert detail["from_board"]["key"] == src and detail["to_board"]["key"] == dst
    assert (detail["old_key"], detail["new_key"]) == (card["key"], moved["key"])
    assert detail["dropped_labels"] == ["Docs"]
    assert detail["removed_assignees"] == [str(leaves.id)]
    assert detail["cleared_repo"] is None
    assert entry["board_id"] == target_id

    # A repository the target doesn't link is cleared in the same write.
    lost = ok(await move_board(client, pm, src, other, dst))
    assert lost["repo_id"] is None and lost["key"] == f"{dst}-3"
    page = ok(await client.get(f"{BOARDS}/{dst}/cards/3/events", headers=pm.headers))
    (cleared,) = [e for e in page["items"] if e["type"] == "moved_board"]
    assert cleared["detail"]["cleared_repo"] == str(lost_repo)


async def test_every_old_key_resolves_after_two_moves(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    two = await two_boards(client, pg_session_factory)
    third = (await make_board(client, two.pm, template="blank"))["board"]["key"]
    card = await make_card(client, two.pm, two.src, "Traveller")
    on_b = ok(await move_board(client, two.pm, two.src, card, two.dst))
    on_c = ok(await move_board(client, two.pm, two.dst, on_b, third))
    assert on_c["key"] == f"{third}-1"
    for old in (card["key"], on_b["key"], on_c["key"].lower()):
        found = ok(await client.get(f"{BY_KEY}/{old}", headers=two.pm.headers))
        assert (found["id"], found["key"]) == (card["id"], on_c["key"])
