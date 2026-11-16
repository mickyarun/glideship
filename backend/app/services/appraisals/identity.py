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

"""A person's identity set, and the accounts that may be them but aren't merged.

Engineers often have two or three accounts (a work email holding BUDs, a
GitHub no-reply address holding PRs). Work on an unmerged account would
be missing from their check-in, so it is flagged rather than guessed at:
HR merges the accounts, and the next check-in includes it.
"""

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.appraisal_identity import AppraisalIdentityRepository, LooseAccount


@dataclass(frozen=True)
class Person:
    """Who the check-in is for."""

    user_id: uuid.UUID
    name: str
    email: str
    github_username: str | None


def _tokens(text: str | None) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _local_part(email: str) -> str:
    # GitHub no-reply addresses look like 12345+login@users.noreply.github.com.
    local = email.split("@", 1)[0]
    return _tokens(local.split("+", 1)[-1])


def possible_duplicates(person: Person, loose: Sequence[LooseAccount]) -> list[LooseAccount]:
    """Unmerged accounts that look like ``person`` (pure).

    A match is the same name, or a GitHub login that is the person's own
    login or their email's local part.
    """
    name = _tokens(person.name)
    logins = {_tokens(person.github_username), _local_part(person.email)} - {""}
    found = []
    for account in loose:
        if account.user_id == person.user_id:
            continue
        login = _tokens(account.github_username) or _local_part(account.email)
        if (name and _tokens(account.name) == name) or (login and login in logins):
            found.append(account)
    return found


async def identity_set(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> list[uuid.UUID]:
    """The person's account and every account merged into it."""
    merged = await AppraisalIdentityRepository(db, org_id=org_id).merged_accounts(user_id)
    return [user_id, *merged]


def warning(account: LooseAccount) -> dict[str, str]:
    """How a possible duplicate is saved on the check-in: ids and names only."""
    return {"user_id": str(account.user_id), "name": account.name}
