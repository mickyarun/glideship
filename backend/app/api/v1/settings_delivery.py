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

"""The Delivery (BUD) board's settings: its AI switch.

Mounted under ``/api/v1/settings`` behind ``workspace:engineering``. Anyone
who can see BUDs may read them (the board shows the switch); changing them
needs ``org:edit_settings``, like the other BUD lifecycle settings.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_permissions
from app.models.user import User
from app.schemas.delivery_settings import DeliverySettings, DeliverySettingsUpdate
from app.services.delivery_settings import get_delivery_settings, update_delivery_settings

router = APIRouter(tags=["settings"])


@router.get(
    "/delivery",
    response_model=DeliverySettings,
    dependencies=[Depends(require_permissions("buds:view"))],
)
async def read_delivery(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeliverySettings:
    """The Delivery board's settings."""
    return await get_delivery_settings(db, current_user.org_id)


@router.patch(
    "/delivery",
    response_model=DeliverySettings,
    dependencies=[Depends(require_permissions("org:edit_settings"))],
)
async def change_delivery(
    body: DeliverySettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeliverySettings:
    """Change the Delivery board's settings; switching AI off stops new BUD stage agents."""
    return await update_delivery_settings(db, current_user.org_id, body)
