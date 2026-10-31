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

"""A Trello board's JSON (export or API read) as typed models.

Trello publishes no schema, so every field is optional except ids, and a
null, a missing key or a malformed date reads as empty rather than
failing the whole file. Keys we don't use are ignored.
"""

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.imports.errors import ImportSourceDataError
from app.services.imports.trello.constants import TRELLO_COMMENT_ACTION, TRELLO_EXPORT_ACTION_CAP
from app.services.imports.trello.fields import Flag, Ids, Pos, Raw, Records, Text, When

NOT_A_BOARD = (
    "This isn't a Trello board export. Export the board as JSON from Trello and try again."
)


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class TrelloLabel(_Model):
    """A label on the board."""

    id: str
    name: Text = ""
    color: str | None = None


class TrelloList(_Model):
    """A list (column)."""

    id: str
    name: Text = ""
    closed: Flag = False
    pos: Pos = 0.0


class TrelloMember(_Model):
    """A board member. Exports carry no email, only names."""

    id: str
    full_name: Text = Field(default="", alias="fullName")
    username: Text = ""


class TrelloCheckItem(_Model):
    """One checklist line."""

    id: str
    name: Text = ""
    state: Text = ""
    pos: Pos = 0.0


class TrelloChecklist(_Model):
    """A named checklist on a card."""

    id: str
    id_card: Text = Field(default="", alias="idCard")
    name: Text = ""
    pos: Pos = 0.0
    check_items: Records[TrelloCheckItem] = Field(default_factory=list, alias="checkItems")


class TrelloAttachment(_Model):
    """A file uploaded to Trello, or a link."""

    id: str
    name: Text = ""
    url: Text = ""
    is_upload: Flag = Field(default=False, alias="isUpload")


class TrelloCard(_Model):
    """A card."""

    id: str
    name: Text = ""
    desc: Text = ""
    closed: Flag = False
    id_list: Text = Field(default="", alias="idList")
    id_labels: Ids = Field(default_factory=list, alias="idLabels")
    id_members: Ids = Field(default_factory=list, alias="idMembers")
    pos: Pos = 0.0
    due: When = None
    due_complete: Flag = Field(default=False, alias="dueComplete")
    start: When = None
    short_link: Text = Field(default="", alias="shortLink")
    url: Text = ""
    attachments: Records[TrelloAttachment] = Field(default_factory=list)
    custom_field_items: Raw = Field(default_factory=list, alias="customFieldItems")
    plugin_data: Raw = Field(default_factory=list, alias="pluginData")
    cover: dict[str, Any] | None = None


class TrelloActionData(_Model):
    """The part of an action a comment needs."""

    text: Text = ""
    card: dict[str, Any] | None = None


class TrelloActionMember(_Model):
    """Who made an action."""

    id: Text = ""
    full_name: Text = Field(default="", alias="fullName")


class TrelloAction(_Model):
    """An entry in the board's action history; only comments are imported."""

    id: str
    type: Text = ""
    date: When = None
    id_member_creator: Text = Field(default="", alias="idMemberCreator")
    data: TrelloActionData = Field(default_factory=TrelloActionData)
    member_creator: TrelloActionMember | None = Field(default=None, alias="memberCreator")

    @property
    def card_id(self) -> str | None:
        """The card a comment is on."""
        card_id = (self.data.card or {}).get("id")
        return card_id if isinstance(card_id, str) else None


class TrelloExport(_Model):
    """The whole board."""

    id: Text = ""
    name: Text = ""
    url: Text = ""
    lists: Records[TrelloList] = Field(default_factory=list)
    cards: Records[TrelloCard] = Field(default_factory=list)
    labels: Records[TrelloLabel] = Field(default_factory=list)
    members: Records[TrelloMember] = Field(default_factory=list)
    checklists: Records[TrelloChecklist] = Field(default_factory=list)
    actions: Records[TrelloAction] = Field(default_factory=list)
    custom_fields: Raw = Field(default_factory=list, alias="customFields")
    plugin_data: Raw = Field(default_factory=list, alias="pluginData")

    def comments(self) -> list[TrelloAction]:
        """Comment actions on a card."""
        return [a for a in self.actions if a.type == TRELLO_COMMENT_ACTION and a.card_id]

    @property
    def action_cap_hit(self) -> bool:
        """Whether the export is at the 1,000-action cap, so older comments are missing."""
        return len(self.actions) >= TRELLO_EXPORT_ACTION_CAP


def parse_export(data: bytes) -> TrelloExport:
    """Parse a board's JSON, refusing anything that isn't shaped like a Trello board.

    Raises:
        ImportSourceDataError: Not JSON, not an object, or no lists and cards.
    """
    try:
        raw = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImportSourceDataError(NOT_A_BOARD) from exc
    return parse_board(raw)


def parse_board(raw: Any) -> TrelloExport:
    """Read already-decoded board JSON; see :func:`parse_export`."""
    if not isinstance(raw, dict) or "lists" not in raw or "cards" not in raw:
        raise ImportSourceDataError(NOT_A_BOARD)
    try:
        return TrelloExport.model_validate(raw)
    except ValidationError as exc:
        raise ImportSourceDataError(NOT_A_BOARD) from exc
