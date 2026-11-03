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

"""Which timezone someone's follow-ups go out in before they pick one (pure, no I/O)."""

import uuid

from app.repositories.followup_zone import ZoneParts
from app.services.leave.digest_settings import org_zone_name


def default_zone(parts: ZoneParts, org_id: uuid.UUID) -> str:
    """Their own leave policy's zone, else the org's.

    The org's is the one the morning card reminder uses, so the two agree on
    what "today" is for people who never chose a zone. The settings page
    shows this same name, so what it says is when the DM really arrives.
    """
    return parts.own_policy or org_zone_name(parts.org_config, parts.default_policy, org_id)
