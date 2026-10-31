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

"""A Trello export imported into a new board: every field lands, and nothing else is said."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.board import Board, BoardLabel, BoardStage
from app.models.board_card import BoardCard, BoardCardAssignee, BoardCardLabel
from app.models.board_card_detail import (
    BoardCardAttachment,
    BoardCardChecklistItem,
    BoardCardComment,
    BoardCardEvent,
)
from app.models.board_enums import BoardCardEventType, BoardMemberRole
from app.models.board_member import BoardMember
from app.models.external_import import ExternalItemMap, ExternalItemStatus, ImportSourceKind
from app.models.notification import Notification
from app.services import event_bus, slack_dm
from tests.integration.board_api_support import ok
from tests.integration.board_import_support import (
    IMPORTS,
    Jobs,
    capture_jobs,
    mapping,
    named,
    new_board,
    parsed,
    save_and_start,
    use_import_storage,
)
from tests.integration.board_support import board_key
from tests.integration.scan_features_bugs_support import Factory, new_org
from tests.services.trello_fixture import (
    ANCIENT,
    ARCHIVED,
    FIRST,
    IN_FLIGHT,
    PRIYA,
    SPEC,
    fixture_json,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def jobs(pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Jobs:
    use_import_storage(tmp_path, monkeypatch)
    return capture_jobs(pg_session_factory, monkeypatch)


@pytest.fixture
def heard(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Every board-topic message and Slack DM sent while the test runs."""
    sent: list[tuple[str, dict[str, Any]]] = []
    publish = event_bus.publish

    def _publish(topic: str, data: dict[str, Any]) -> None:
        if topic.startswith("board:"):
            sent.append((topic, data))
        publish(topic, data)

    async def _dm(*args: Any, **kwargs: Any) -> None:
        sent.append(("dm", {"args": args}))

    monkeypatch.setattr(event_bus, "publish", _publish)
    monkeypatch.setattr(slack_dm, "send_dm", _dm)
    return sent


async def test_a_new_board_gets_every_card_silently(
    client: AsyncClient,
    pg_session_factory: Factory,
    jobs: Jobs,
    heard: list[tuple[str, dict[str, Any]]],
) -> None:
    org = await new_org(pg_session_factory)
    pm = await named(pg_session_factory, org, "Pat Manager", "pm")
    priya = await named(pg_session_factory, org, "Priya Sharma")
    session_id = await parsed(client, pm, jobs)
    read = ok(await client.get(f"{IMPORTS}/{session_id}", headers=pm.headers))
    assert read["status"] == "ready" and read["total_cards"] == 6
    members = {m["id"]: m["suggested_user_id"] for m in read["discovery"]["members"]}
    assert members[PRIYA] == str(priya.id)

    key = board_key()
    await save_and_start(client, pm, session_id, mapping(new_board(key), priya=priya.id))
    await jobs.run_all()
    done = ok(await client.get(f"{IMPORTS}/{session_id}", headers=pm.headers))
    assert done["status"] == "completed" and done["board_key"] == key
    assert done["result"]["imported"] == 5 and done["result"]["skipped"] == 1
    assert done["result"]["dropped"]["custom_fields"] == 1
    assert done["result"]["dropped"]["links_dropped"] == 1  # the javascript: link

    async with pg_session_factory() as db:
        board = (await db.scalars(select(Board).where(Board.key == key))).one()
        stages = list(
            await db.scalars(
                select(BoardStage)
                .where(BoardStage.board_id == board.id)
                .order_by(BoardStage.position)
            )
        )
        assert [(s.name, s.category.value, s.is_default) for s in stages] == [
            ("Backlog", "todo", True),
            ("Doing", "in_progress", False),
            ("Done", "done", False),
        ]
        maps = {
            m.external_id: m
            for m in await db.scalars(
                select(ExternalItemMap).where(ExternalItemMap.target_board_id == board.id)
            )
        }
        assert maps[ANCIENT].status is ExternalItemStatus.SKIPPED
        cards = {
            m.external_id: await db.get(BoardCard, m.card_id) for m in maps.values() if m.card_id
        }
        # Numbered and placed in source order.
        assert (cards[FIRST].number, cards[SPEC].number) == (1, 2)
        assert cards[FIRST].position < cards[SPEC].position
        spec, flight, archived = cards[SPEC], cards[IN_FLIGHT], cards[ARCHIVED]
        spec_json = next(c for c in fixture_json()["cards"] if c.get("id") == SPEC)
        assert spec.priority is None and spec.description_md and "<script>" in spec.description_md
        assert spec.due_at == datetime(2026, 11, 5, 17, tzinfo=UTC) and not spec.due_done
        assert spec.start_at == datetime(2026, 11, 1, 9, tzinfo=UTC)
        assert flight.due_done and flight.started_at is not None
        assert archived.archived_at is not None and archived.completed_at is not None

        labels = {
            lb.name: lb.color.value
            for lb in await db.scalars(select(BoardLabel).where(BoardLabel.board_id == board.id))
        }
        assert labels == {"Bug": "red", "Green": "green", "Design": "sky"}
        spec_labels = await db.scalar(
            select(func.count()).where(BoardCardLabel.card_id == spec.id)
        )
        assert spec_labels == 2
        # Priya is mapped; Sam isn't, so In flight has only her.
        assignees = set(
            await db.scalars(
                select(BoardCardAssignee.user_id).where(BoardCardAssignee.card_id == flight.id)
            )
        )
        assert assignees == {priya.id}
        role = await db.scalar(
            select(BoardMember.role).where(
                BoardMember.board_id == board.id, BoardMember.user_id == priya.id
            )
        )
        assert role is BoardMemberRole.EDITOR

        checklist = list(
            await db.scalars(
                select(BoardCardChecklistItem)
                .where(BoardCardChecklistItem.card_id == spec.id)
                .order_by(BoardCardChecklistItem.position)
            )
        )
        assert [(c.group_name, c.text, c.done) for c in checklist] == [
            ("Launch", "Draft", True),
            ("Launch", "Review", False),
            ("QA", "Test it", False),
        ]
        comments = list(
            await db.scalars(
                select(BoardCardComment)
                .where(BoardCardComment.card_id == spec.id)
                .order_by(BoardCardComment.created_at)
            )
        )
        assert [(c.body, c.author_id, c.author_label) for c in comments] == [
            ("Looks good", priya.id, None),
            ("From someone not in the org", None, "Sam Outsider (Trello)"),
        ]
        # Mapped or not, every imported comment says where it came from.
        assert {c.import_source for c in comments} == {ImportSourceKind.TRELLO}
        assert comments[0].created_at == datetime(2026, 10, 1, 10, tzinfo=UTC)
        attachments = list(
            await db.scalars(
                select(BoardCardAttachment).where(BoardCardAttachment.card_id == spec.id)
            )
        )
        # Upload mode never fetches: the uploaded file stays a link to Trello.
        uploaded = next(a for a in spec_json["attachments"] if a["isUpload"])
        assert sorted((a.kind.value, a.url) for a in attachments) == [
            ("link", "https://example.com/brief"),
            ("link", uploaded["url"]),
        ]
        events = list(
            await db.scalars(select(BoardCardEvent).where(BoardCardEvent.board_id == board.id))
        )
        assert {e.type for e in events} == {BoardCardEventType.IMPORTED}
        assert len(events) == 5
        assert {e.detail["source_key"] for e in events if e.card_id == spec.id} == {"Card0001"}
        assert {e.detail["source"] for e in events} == {"trello"}
        notices = await db.scalar(
            select(func.count()).select_from(Notification).where(Notification.org_id == org)
        )
        assert notices == 0

    # One summary on the board's topic, and no DMs.
    assert [(t, d["event"]) for t, d in heard] == [(f"board:{board.id}", "board_imported")]
    assert heard[0][1]["imported"] == 5 and heard[0][1]["status"] == "completed"
    assert done["result"]["suppressed_events"] == 5


async def test_archived_cards_can_be_skipped(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs
) -> None:
    org = await new_org(pg_session_factory)
    pm = await named(pg_session_factory, org, "Pat Manager", "pm")
    session_id = await parsed(client, pm, jobs)
    await save_and_start(client, pm, session_id, mapping(new_board(board_key()), archived="skip"))
    await jobs.run_all()
    done = ok(await client.get(f"{IMPORTS}/{session_id}", headers=pm.headers))
    assert (done["result"]["imported"], done["result"]["skipped"]) == (4, 2)
    async with pg_session_factory() as db:
        row = await db.scalar(
            select(ExternalItemMap).where(
                ExternalItemMap.external_id == ARCHIVED, ExternalItemMap.session_id == done["id"]
            )
        )
        assert (
            row is not None
            and row.status is ExternalItemStatus.SKIPPED
            and row.error == "archived"
        )
