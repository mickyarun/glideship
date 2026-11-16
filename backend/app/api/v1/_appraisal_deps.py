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

"""The caller, as the appraisal services want it."""

from fastapi import Depends

from app.core.deps import PermissionSet, get_current_user, get_permission_set
from app.models.user import User
from app.services.appraisals.context import Caller


async def get_caller(
    current_user: User = Depends(get_current_user),
    perms: PermissionSet = Depends(get_permission_set),
) -> Caller:
    """Who is asking, in which org, with which permissions."""
    return Caller(user_id=current_user.id, org_id=current_user.org_id, perms=perms)
