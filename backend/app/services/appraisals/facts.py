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

"""Gathering a person's work for one check-in period, by SQL alone.

The list is saved on the check-in when it is created, so the check-in is
complete without any AI and later edits to a card or PR don't rewrite a
closed month. Sources the role template switches off are skipped, so a
support person isn't shown an empty PR list.
"""

import uuid
from collections.abc import Awaitable, Callable, Collection, Iterable
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import FactSource
from app.repositories.work_facts import FactRow, WorkFactsRepository
from app.repositories.work_facts_other import OtherFactsRepository

Query = Callable[[Collection[uuid.UUID], datetime, datetime], Awaitable[list[FactRow]]]

# Learnings, estimates and skills describe a whole period; they feed the
# period summary, not the monthly list.
MONTHLY_SOURCES = frozenset(
    {
        FactSource.BUDS,
        FactSource.PULL_REQUESTS,
        FactSource.CODE_REVIEWS,
        FactSource.BUGS,
        FactSource.BOARD_CARDS,
        FactSource.QA_EVIDENCE,
        FactSource.HR_RECORDS,
    }
)


def bounds(start: date, end: date, zone: tzinfo) -> tuple[datetime, datetime]:
    """The period as UTC instants: from ``start``'s midnight to the day after ``end``."""
    first = datetime.combine(start, time.min, zone).astimezone(UTC)
    after = datetime.combine(end + timedelta(days=1), time.min, zone).astimezone(UTC)
    return first, after


def _queries(db: AsyncSession, org_id: uuid.UUID) -> dict[FactSource, Query]:
    work = WorkFactsRepository(db, org_id=org_id)
    other = OtherFactsRepository(db, org_id=org_id)
    return {
        FactSource.BUDS: work.buds_shipped,
        FactSource.PULL_REQUESTS: work.pull_requests,
        FactSource.CODE_REVIEWS: work.code_reviews,
        FactSource.BUGS: work.bugs,
        FactSource.BOARD_CARDS: other.board_cards,
        FactSource.QA_EVIDENCE: work.qa_evidence,
        FactSource.HR_RECORDS: other.hr_records,
    }


def safe_url(url: str) -> str | None:
    """The link if it is http(s) or a path in the app; anything else is dropped.

    PR links come from several writers; a ``javascript:`` one must never
    reach an ``href`` on an HR page.
    """
    lowered = url.strip().lower()
    in_app = url.startswith("/") and not url.startswith("//")
    return url if in_app or lowered.startswith(("https://", "http://")) else None


def as_ref(row: FactRow) -> dict[str, Any]:
    """How a fact is saved in ``fact_refs``."""
    return {
        "source": row.source.value,
        "id": row.id,
        "key": row.key,
        "title": row.title,
        "url": safe_url(row.url),
        "verb": row.verb,
        "done_at": row.done_at.isoformat() if row.done_at else None,
        "board_id": str(row.board_id) if row.board_id else None,
    }


async def gather(
    db: AsyncSession,
    org_id: uuid.UUID,
    identities: Collection[uuid.UUID],
    sources: Iterable[FactSource],
    start: date,
    end: date,
    zone: tzinfo,
) -> list[dict[str, Any]]:
    """Every fact in the period from the enabled sources, oldest first."""
    first, after = bounds(start, end, zone)
    queries = _queries(db, org_id)
    rows: list[FactRow] = []
    for source in sorted(set(sources) & MONTHLY_SOURCES):
        rows += await queries[source](identities, first, after)
    rows.sort(key=lambda r: (r.done_at or first, r.key))
    return [as_ref(r) for r in rows]
