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


"""Who may start a new import right now: rights, open-import caps and a rate limit.

Checked before an upload is read, so a caller who can't import never makes
the server spool a file. The caps count unfinished sessions per person and
per org (``BoardsConfig.import_max_open_per_user`` / ``_per_org``); they are
soft, as two requests at once can both pass. The rate limit counts starts
per person over a fixed window and, like every throttle here, lets the
request through when Redis is down.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.external_import import ExternalImportSessionRepository
from app.services.boards.access import BoardCaller
from app.services.boards.errors import BoardRateLimitedError
from app.services.fixed_window import seconds_until_allowed
from app.services.imports.errors import OpenImportScope, TooManyOpenImportsError
from app.services.imports.target import check_may_import

TOO_MANY_OPEN = "You have {n} imports still open. Finish or wait for one before starting another."
ORG_TOO_MANY_OPEN = "Your organisation has {n} imports still open. Try again once one finishes."
TOO_MANY_STARTS = "You've started a lot of imports lately. Try again a little later."


@dataclass(frozen=True)
class Admitted:
    """Proof that ``caller`` passed :func:`admit`; creating a session needs one."""

    caller: BoardCaller


async def admit(db: AsyncSession, caller: BoardCaller) -> Admitted:
    """Refuse a caller who can't import (403), has too many open (409) or starts too often (429).

    The rate limit is counted last, so refused attempts don't use it up.
    """
    cfg = settings.boards
    await check_may_import(db, caller)
    repo = ExternalImportSessionRepository(db, org_id=caller.org_id)
    if await repo.count_open(created_by=caller.user_id) >= cfg.import_max_open_per_user:
        raise TooManyOpenImportsError(
            TOO_MANY_OPEN.format(n=cfg.import_max_open_per_user), scope=OpenImportScope.USER
        )
    if await repo.count_open() >= cfg.import_max_open_per_org:
        raise TooManyOpenImportsError(
            ORG_TOO_MANY_OPEN.format(n=cfg.import_max_open_per_org), scope=OpenImportScope.ORG
        )
    wait = await seconds_until_allowed(
        f"board_import_create:{caller.org_id}:{caller.user_id}",
        limit=cfg.import_creates_per_window,
        window_seconds=cfg.import_create_window_seconds,
    )
    if wait:
        raise BoardRateLimitedError(TOO_MANY_STARTS, retry_after_seconds=wait)
    return Admitted(caller=caller)
