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

"""The BUD page's "start designing" hint for a BUD in design with no design yet.

Moving a BUD into design from its own page starts design generation right
there. Anywhere else (a handover landing at design, a drag on the Delivery
board) has no repository picker to show, so whoever opens the BUD first
starts it. ``design_pending`` stays true until a design exists.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bud import BUDDocument, BUDStatus
from app.repositories.bud_design_pending import BUDDesignPendingRepository
from app.services.bud_agent_trigger import should_auto_generate_phase


async def design_pending(db: AsyncSession, bud: BUDDocument) -> bool:
    """In design with generation on, and no design started yet.

    Costs no query unless the BUD is in design with generation on.
    """
    if bud.status != BUDStatus.DESIGN:
        return False
    if not should_auto_generate_phase(bud.auto_generate_phases or {}, BUDStatus.DESIGN.value):
        return False
    return await BUDDesignPendingRepository(db, org_id=bud.org_id).has_no_designs(bud.id)
