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

"""The org's Trello API key and token, for importing boards over the API.

Stored encrypted; the key and token are never sent back, only whether
Trello is connected and as which member.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_permissions
from app.models.user import User
from app.schemas.boards.imports import TrelloCredentialsWrite, TrelloSettingsRead
from app.services.imports.trello import credentials

router = APIRouter(tags=["settings"])

CONFIGURE = Depends(require_permissions("integrations:configure"))


@router.get("/trello", response_model=TrelloSettingsRead, dependencies=[CONFIGURE])
async def get_trello(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> TrelloSettingsRead:
    """Whether Trello is connected."""
    return await credentials.settings_read(db, current_user.org_id)


@router.put("/trello", response_model=TrelloSettingsRead, dependencies=[CONFIGURE])
async def put_trello(
    body: TrelloCredentialsWrite,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrelloSettingsRead:
    """Check the key and token with Trello and store them encrypted."""
    return await credentials.connect(db, current_user.org_id, body)


@router.delete("/trello", status_code=status.HTTP_204_NO_CONTENT, dependencies=[CONFIGURE])
async def delete_trello(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    """Forget the stored key and token."""
    await credentials.disconnect(db, current_user.org_id)
