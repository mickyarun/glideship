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

"""Tell the who's-out channel about leave or WFH approved after the morning post.

The morning post is sent once. Someone whose request is approved later the
same day would otherwise be missing, so they get a short follow-up. Before
the morning post is due nothing is sent: the post itself will include them.
"""

import uuid
from datetime import datetime

import structlog

from app.database import AsyncSessionLocal
from app.models.leave_digest_post import DigestStatus
from app.repositories.leave_digest_post import LeaveDigestPostRepository
from app.services.leave.digest_build import build_digest
from app.services.leave.digest_post import post_to_channels
from app.services.leave.digest_settings import digest_zone, load_digest_settings
from app.services.slack_dm import bot_token

logger = structlog.get_logger(__name__)

# The morning post is over: it went out, or there was nobody to mention.
_MORNING_DONE = {DigestStatus.POSTED, DigestStatus.SKIPPED}


async def announce_late_request(org_id: uuid.UUID, request_id: uuid.UUID) -> None:
    """Post ``request_id`` to the channel if it covers today and the morning post is done.

    Background work after a commit: failures are logged, never raised.
    """
    try:
        async with AsyncSessionLocal() as db:
            settings = await load_digest_settings(db, org_id)
            if not settings.enabled or not settings.channel_ids:
                return
            today = datetime.now(await digest_zone(db, org_id, settings)).date()
            status = await LeaveDigestPostRepository(db, org_id=org_id).status_for(today)
            if status not in _MORNING_DONE:
                return
            text = await build_digest(db, org_id, today, only_request=request_id)
            token = await bot_token(db, org_id)
        if text is None or not token:
            return
        errors = await post_to_channels(token, settings.channel_ids, text)
        if errors:
            logger.warning("leave_digest_late_failed", org_id=str(org_id), errors=errors)
    except Exception:
        logger.exception("leave_digest_late_failed", org_id=str(org_id))
