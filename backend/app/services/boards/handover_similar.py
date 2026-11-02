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

"""The draft's embedding, and the open BUDs close to it.

The preview embeds the text a new BUD would be embedded from
(:func:`app.services.bud_create.embed_text_for`) and keeps the vector in a
small in-process cache keyed by the org and a hash of that text. A confirm
whose text is unchanged takes the vector from there, so the text isn't
embedded twice; a changed title or requirements is a cache miss and is
embedded again. The cache is per process, like the job queue (one backend
process); a miss only costs one more embedding.
"""

import hashlib
import uuid

import structlog
from cachetools import TTLCache
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.bud import BUDRepository
from app.schemas.boards.handover import SimilarBUD
from app.services.bud_create import embed_text_for
from app.services.embedding_service import embedding_service
from app.services.jira_dedup import THRESHOLD_REVIEW

logger = structlog.get_logger(__name__)

_cache: TTLCache[str, list[float]] = TTLCache(
    maxsize=settings.boards.handover_embedding_cache_size,
    ttl=settings.boards.handover_embedding_cache_seconds,
)


def bud_key(number: int) -> str:
    """A BUD's display key, e.g. ``BUD-007``."""
    return f"BUD-{number:03d}"


def _cache_key(org_id: uuid.UUID, text: str) -> str:
    return f"{org_id}:{hashlib.sha256(text.encode()).hexdigest()}"


async def draft_embedding(
    org_id: uuid.UUID, title: str, requirements_md: str | None
) -> list[float] | None:
    """The new BUD's embedding, cached by the preview; None when embedding fails."""
    text = embed_text_for(title, requirements_md)
    key = _cache_key(org_id, text)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    try:
        vector = await embedding_service.embed(text)
    except Exception:
        logger.warning("handover_embedding_failed", org_id=str(org_id), exc_info=True)
        return None
    _cache[key] = vector
    return vector


async def similar_buds(
    db: AsyncSession, org_id: uuid.UUID, vector: list[float] | None
) -> list[SimilarBUD]:
    """Open BUDs closer than the review threshold, nearest first."""
    if vector is None:
        return []
    found = await BUDRepository(db, org_id=org_id).find_nearest_active(
        vector, settings.boards.handover_similar_limit, max_distance=THRESHOLD_REVIEW
    )
    return [
        SimilarBUD(
            bud_id=bud.id,
            key=bud_key(bud.bud_number),
            title=bud.title,
            status=bud.status,
            distance=round(distance, 4),
        )
        for bud, distance in found
    ]
