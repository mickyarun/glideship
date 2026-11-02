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


"""One committed batch of an import.

1. Items already on the board (any session) are left alone, and the read
   transaction ends, so nothing is held open while the source downloads.
2. The source prefetches what the rest need from outside, with no locks.
3. The stages are locked, and the item maps read again: a second session
   importing the same source into the same board waits on that lock, so
   it can't write what the first just committed.
4. The card numbers are claimed in one call; each item is written in its
   own savepoint, so one bad card is recorded as failed (its number going
   to the next card) and the others still land.
5. The importer's access is checked again, then progress, the running
   result and the cards commit together. Prefetched files no card took
   are deleted, whether the commit worked or not.
"""

from collections import Counter

import structlog

from app.models.external_import import ExternalItemStatus
from app.repositories.external_import import ExternalItemMapRepository
from app.schemas.boards.imports import ImportResult
from app.services.boards.errors import BoardError
from app.services.imports import card_writer
from app.services.imports.board_plan import BoardPlan
from app.services.imports.context import ImportContext
from app.services.imports.items import ExternalItem
from app.services.imports.source import ImportSource
from app.services.imports.target import recheck_access

logger = structlog.get_logger(__name__)

ITEM_FAILED = "This card couldn't be imported."


async def write_batch(
    ctx: ImportContext,
    source: ImportSource,
    plan: BoardPlan,
    items: list[ExternalItem],
    already: int,
) -> int:
    """Write ``items`` and commit; returns how many items other sessions had already imported."""
    maps = ExternalItemMapRepository(ctx.db, org_id=ctx.org_id)
    session, board_id = ctx.session, ctx.board.id
    done = await maps.imported_ids(source.kind, board_id, (i.external_id for i in items))
    todo = [i for i in items if i.skip_reason is None and i.external_id not in done]
    await ctx.db.commit()
    async with source.prefetch(todo, ctx) as fetched:
        await ctx.lock_stages()
        late = await maps.imported_ids(source.kind, board_id, (i.external_id for i in todo))
        done.update(late)
        todo = [i for i in todo if i.external_id not in late]
        await ctx.claim_numbers(len(todo))
        for item in todo:
            ctx.start_item()
            tally: Counter[str] = Counter()
            got = fetched.get(item.external_id)
            try:
                async with ctx.db.begin_nested():
                    card_id = await card_writer.write_card(ctx, plan, item.draft, got.files, tally)
                    await maps.record(
                        session_id=session.id,
                        kind=source.kind,
                        board_id=board_id,
                        external_id=item.external_id,
                        status=ExternalItemStatus.IMPORTED,
                        card_id=card_id,
                    )
            except Exception as exc:
                logger.warning("import_item_failed", external_id=item.external_id, error=str(exc))
                ctx.item_failed()
                await maps.record(
                    session_id=session.id,
                    kind=source.kind,
                    board_id=board_id,
                    external_id=item.external_id,
                    status=ExternalItemStatus.FAILED,
                    error=str(exc) if isinstance(exc, BoardError) else ITEM_FAILED,
                )
                continue
            fetched.keep(item.external_id)
            ctx.counters.update(tally + got.dropped)
        await ctx.release_unused_numbers()
        await fetched.release_unkept(ctx)
        for item in items:
            if item.skip_reason is not None and item.external_id not in done:
                await maps.record(
                    session_id=session.id,
                    kind=source.kind,
                    board_id=board_id,
                    external_id=item.external_id,
                    status=ExternalItemStatus.SKIPPED,
                    error=item.skip_reason,
                )
        await recheck_access(ctx.db, session, ctx.actor_id)
        already += sum(1 for owner in done.values() if owner != session.id)
        session.last_processed_index = items[-1].index
        session.processed_count = items[-1].index + 1
        session.attachment_bytes = ctx.budget.spent
        session.result = (await running_result(ctx, already)).model_dump(mode="json")
        await ctx.commit_batch()
    return already


async def running_result(ctx: ImportContext, already: int) -> ImportResult:
    """The session's result so far, counted from its item maps."""
    counts = await ExternalItemMapRepository(ctx.db, org_id=ctx.org_id).counts(ctx.session.id)
    return ImportResult(
        imported=counts[ExternalItemStatus.IMPORTED],
        skipped=counts[ExternalItemStatus.SKIPPED],
        failed=counts[ExternalItemStatus.FAILED],
        already_imported=already,
        dropped={kind: n for kind, n in ctx.counters.items() if n},
        attachment_bytes=ctx.budget.spent,
        suppressed_events=ctx.suppressed,
    )
