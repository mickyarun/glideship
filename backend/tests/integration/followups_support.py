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

"""Set up daily follow-ups: opted-in people, BUDs, leave and holidays; capture the DMs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.bud import BUDStatus
from app.models.digest_claim import DigestClaim, DigestClaimKind
from app.models.followup_settings import FollowupSettings
from app.models.policy_holiday import HolidayKind, HolidaySource, PolicyHoliday
from app.services import slack_dm
from app.services.followups import scheduler
from app.services.leave.policies import ensure_default_policy
from tests.integration.board_api_support import Person, make_card
from tests.integration.board_notify_support import fake_slack
from tests.integration.bud_lifecycle_support import add_bud
from tests.integration.scan_features_bugs_support import Factory

LONDON = "Europe/London"


@dataclass
class Dms:
    """Follow-up DMs posted, as ``(slack id, fallback text, blocks)``."""

    posts: list[tuple[str, str, list[dict[str, Any]]]] = field(default_factory=list)
    fail: bool = False

    def to(self, slack_id: str) -> list[list[dict[str, Any]]]:
        """The block lists DMed to one Slack user."""
        return [blocks for who, _text, blocks in self.posts if who == slack_id]


def capture_dms(monkeypatch: pytest.MonkeyPatch, factory: Factory) -> Dms:
    """Route the scheduler at the test database and record DMs with their blocks."""
    fake_slack(monkeypatch, factory)
    monkeypatch.setattr(scheduler, "AsyncSessionLocal", factory)
    dms = Dms()

    async def _post(_token: str, channel: str, text: str, **kw: Any) -> dict[str, Any] | None:
        if dms.fail:
            return None
        dms.posts.append((channel.removeprefix("D-"), text, kw.get("blocks") or []))
        return {"ok": True}

    monkeypatch.setattr(slack_dm, "chat_post_message", _post)
    return dms


def sections(blocks: list[dict[str, Any]]) -> list[str]:
    """The section texts of one message, in order."""
    return [b["text"]["text"] for b in blocks if b["type"] == "section"]


async def save_schedule(
    factory: Factory,
    org: uuid.UUID,
    user_id: uuid.UUID,
    *,
    at: time = time(9, 0),
    zone: str = LONDON,
    weekdays_only: bool = True,
    enabled: bool = True,
) -> None:
    """Save a person's follow-ups schedule in ``org`` (or turn it off there)."""
    async with factory() as db:
        db.add(
            FollowupSettings(
                org_id=org,
                user_id=user_id,
                send_time=at,
                timezone=zone,
                weekdays_only=weekdays_only,
                enabled=enabled,
            )
        )
        await db.commit()


async def due_card(
    client: AsyncClient, who: Person, key: str, title: str, due: str, *people: Person
) -> dict[str, Any]:
    """A card due at ``due`` (ISO, UTC) assigned to ``people``."""
    ids = [str(p.id) for p in people]
    return await make_card(client, who, key, title, due_at=due, assignee_ids=ids)


async def target_bud(
    factory: Factory,
    org: uuid.UUID,
    number: int,
    assignee: uuid.UUID,
    target: datetime,
    status: BUDStatus = BUDStatus.DEVELOPMENT,
) -> None:
    """A BUD assigned to ``assignee`` whose current phase target is ``target``."""
    await add_bud(
        factory,
        org,
        number=number,
        status=status,
        title=f"Feature {number}",
        assignee_id=assignee,
        current_phase_deadline=target,
    )


async def mandatory_holiday(factory: Factory, org: uuid.UUID, day: date) -> None:
    """A mandatory holiday on the org's default leave policy."""
    async with factory() as db:
        policy = await ensure_default_policy(db, org)
        db.add(
            PolicyHoliday(
                org_id=org,
                policy_id=policy.id,
                date=day,
                name="Founders Day",
                kind=HolidayKind.MANDATORY,
                source=HolidaySource.MANUAL,
            )
        )
        await db.commit()


async def followup_claims(factory: Factory, org: uuid.UUID) -> list[DigestClaim]:
    """The org's follow-ups claims."""
    async with factory() as db:
        rows = await db.scalars(
            select(DigestClaim).where(
                DigestClaim.org_id == org, DigestClaim.kind == DigestClaimKind.DAILY_FOLLOWUPS
            )
        )
        return list(rows)
