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

"""The org's Trello key and token, encrypted under ``org.config["trello"]``.

The same shape as ``config["jira"]``: each secret is an ``enc:`` string
from :func:`encrypt_secret`, so secret rotation re-encrypts it with no
extra wiring. Neither value is ever returned by the API.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_secret, encrypt_secret
from app.core.permissions_boards import INTEGRATIONS_CONFIGURE
from app.repositories.organization import OrganizationRepository
from app.schemas.boards.imports import TrelloCredentialsWrite, TrelloSettingsRead
from app.services.boards.access import BoardCaller
from app.services.boards.errors import BoardActionForbiddenError
from app.services.imports.errors import ImportSourceDataError
from app.services.imports.trello import client as trello_client
from app.services.imports.trello.wire import TrelloCredentials

CONFIG_KEY = "trello"
NOT_CONFIGURED = "Trello isn't connected. An admin can add an API key and token in Settings."
NO_API_RIGHTS = "Importing from the Trello API needs permission to configure integrations."


def _section(config: dict[str, Any] | None) -> dict[str, Any]:
    section = (config or {}).get(CONFIG_KEY)
    return section if isinstance(section, dict) else {}


def read_credentials(config: dict[str, Any] | None) -> TrelloCredentials | None:
    """The decrypted key and token, or None when Trello isn't connected."""
    section = _section(config)
    key, token = section.get("api_key"), section.get("token")
    if not isinstance(key, str) or not isinstance(token, str):
        return None
    return TrelloCredentials(api_key=decrypt_secret(key), token=decrypt_secret(token))


async def load_credentials(db: AsyncSession, org_id: uuid.UUID) -> TrelloCredentials:
    """The org's credentials.

    Raises:
        ImportSourceDataError: Trello isn't connected.
    """
    creds = read_credentials(await OrganizationRepository(db).get_config(org_id))
    if creds is None:
        raise ImportSourceDataError(NOT_CONFIGURED)
    return creds


async def check_api_access(db: AsyncSession, caller: BoardCaller) -> TrelloCredentials:
    """The org's credentials, for a caller who may put them to work.

    Raises:
        BoardActionForbiddenError: The caller can't configure integrations.
        ImportSourceDataError: Trello isn't connected.
    """
    if not caller.perms.has(INTEGRATIONS_CONFIGURE):
        raise BoardActionForbiddenError(NO_API_RIGHTS)
    return await load_credentials(db, caller.org_id)


async def settings_read(db: AsyncSession, org_id: uuid.UUID) -> TrelloSettingsRead:
    """Whether Trello is connected, and as whom."""
    section = _section(await OrganizationRepository(db).get_config(org_id))
    if "token" not in section:
        return TrelloSettingsRead(configured=False)
    connected = section.get("connected_at")
    return TrelloSettingsRead(
        configured=True,
        member_username=section.get("member_username"),
        connected_at=datetime.fromisoformat(connected) if isinstance(connected, str) else None,
    )


async def connect(
    db: AsyncSession, org_id: uuid.UUID, body: TrelloCredentialsWrite
) -> TrelloSettingsRead:
    """Check the key and token against Trello, then store them encrypted.

    Raises:
        ImportSourceDataError: Trello refused them.
    """
    creds = TrelloCredentials(api_key=body.api_key.strip(), token=body.token.strip())
    async with trello_client.new_client(creds) as client:
        me = await client.me()
    username = me.get("username")
    await OrganizationRepository(db).set_config_section(
        org_id,
        CONFIG_KEY,
        {
            "api_key": encrypt_secret(creds.api_key),
            "token": encrypt_secret(creds.token),
            "member_username": username if isinstance(username, str) else None,
            "connected_at": datetime.now(UTC).isoformat(),
        },
    )
    await db.commit()
    return await settings_read(db, org_id)


async def disconnect(db: AsyncSession, org_id: uuid.UUID) -> None:
    """Forget the org's Trello credentials."""
    await OrganizationRepository(db).remove_config_section(org_id, CONFIG_KEY)
    await db.commit()
