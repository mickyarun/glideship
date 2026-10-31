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

1. Items already imported into this board (any earlier session) are left alone.
2. The source prefetches what the rest need from outside, with no locks held.
3. The context locks the stages and claims the card numbers in one call.
4. Each item is written in its own savepoint, so one bad card is recorded
   as failed and the others still land.
5. Progress and the running result commit with the cards.
"""

import structlog

from app.models.external_import import ExternalItemStatus
from app.repositories.external_import import ExternalItemMapRepository
from app.schemas.boards.imports import ImportResult
from app.services.boards.errors import BoardError
from app.services.imports.context import ImportContext
from app.services.imports.source import ExternalItem, ImportSource

logger = structlog.get_logger(__name__)

ITEM_FAILED = "This card couldn't be imported."


async def write_batch(
    ctx: ImportContext, source: ImportSource, items: list[ExternalItem], result: ImportResult
) -> ImportResult:
    """Write ``items`` and commit; returns the result so far."""
    maps = ExternalItemMapRepository(ctx.db, org_id=ctx.org_id)
    board_id = ctx.board.id
    done = await maps.imported_ids(source.kind, board_id, (i.external_id for i in items))
    todo = [i for i in items if i.skip_reason is None and i.external_id not in done]
    for item in todo:
        await source.prefetch(item, ctx)
    await ctx.begin_batch(len(todo))
    imported = failed = 0
    for item in todo:
        try:
            async with ctx.db.begin_nested():
                card_id = await source.write_item(item, ctx)
                await maps.record(
                    session_id=ctx.session.id,
                    kind=source.kind,
                    board_id=board_id,
                    external_id=item.external_id,
                    status=ExternalItemStatus.IMPORTED,
                    card_id=card_id,
                )
            imported += 1
        except Exception as exc:
            logger.warning("import_item_failed", external_id=item.external_id, error=str(exc))
            await source.discard(item)
            await maps.record(
                session_id=ctx.session.id,
                kind=source.kind,
                board_id=board_id,
                external_id=item.external_id,
                status=ExternalItemStatus.FAILED,
                error=str(exc) if isinstance(exc, BoardError) else ITEM_FAILED,
            )
            failed += 1
    skipped = [i for i in items if i.skip_reason is not None and i.external_id not in done]
    for item in skipped:
        await maps.record(
            session_id=ctx.session.id,
            kind=source.kind,
            board_id=board_id,
            external_id=item.external_id,
            status=ExternalItemStatus.SKIPPED,
            error=item.skip_reason,
        )
    result = ImportResult(
        imported=result.imported + imported,
        failed=result.failed + failed,
        skipped=result.skipped + len(skipped),
        already_imported=result.already_imported + len(done),
        dropped={kind: n for kind, n in ctx.counters.items() if n},
    )
    ctx.session.last_processed_index = items[-1].index
    ctx.session.processed_count = items[-1].index + 1
    ctx.session.result = result.model_dump(mode="json")
    await ctx.commit_batch()
    return result
