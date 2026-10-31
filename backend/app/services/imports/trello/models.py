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


"""A Trello board's JSON as typed models: lenient, and compact once stored.

Trello publishes no schema, so every field is optional except ids, and a
null, a missing key or a malformed date reads as empty rather than
failing the whole file. Keys we don't use are ignored; what the import
drops (custom fields, Power-Up data, covers) is kept only as a count.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.services.imports.trello.constants import TRELLO_COMMENT_ACTION, TRELLO_EXPORT_ACTION_CAP
from app.services.imports.trello.fields import (
    Count,
    Covered,
    Flag,
    Ids,
    Pos,
    Records,
    Ref,
    Text,
    When,
)


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class TrelloLabel(_Model):
    """A label on the board."""

    id: str
    name: Text = ""
    color: Text | None = None


class TrelloList(_Model):
    """A list (column)."""

    id: str
    name: Text = ""
    closed: Flag = False
    pos: Pos = float("inf")


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
    pos: Pos = float("inf")


class TrelloChecklist(_Model):
    """A named checklist on a card."""

    id: str
    id_card: Text = Field(default="", alias="idCard")
    name: Text = ""
    pos: Pos = float("inf")
    check_items: Records[TrelloCheckItem] = Field(default_factory=list, alias="checkItems")


class TrelloAttachment(_Model):
    """A file uploaded to Trello, or a link."""

    id: str
    name: Text = ""
    url: Text = ""
    is_upload: Flag = Field(default=False, alias="isUpload")


class TrelloCard(_Model):
    """A card; custom fields, Power-Up data and the cover are only counted."""

    id: str
    name: Text = ""
    desc: Text = ""
    closed: Flag = False
    id_list: Text = Field(default="", alias="idList")
    id_labels: Ids = Field(default_factory=list, alias="idLabels")
    id_members: Ids = Field(default_factory=list, alias="idMembers")
    pos: Pos = float("inf")
    due: When = None
    due_complete: Flag = Field(default=False, alias="dueComplete")
    start: When = None
    short_link: Text = Field(default="", alias="shortLink")
    url: Text = ""
    attachments: Records[TrelloAttachment] = Field(default_factory=list)
    custom_field_items: Count = Field(default=0, alias="customFieldItems")
    plugin_data: Count = Field(default=0, alias="pluginData")
    cover: Covered = False


class TrelloActionData(_Model):
    """The part of an action a comment needs."""

    text: Text = ""
    card: Ref = None


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
        return (self.data.card or {}).get("id")


class TrelloExport(_Model):
    """The whole board; once compact, ``actions`` holds only comments."""

    id: Text = ""
    name: Text = ""
    url: Text = ""
    lists: Records[TrelloList] = Field(default_factory=list)
    cards: Records[TrelloCard] = Field(default_factory=list)
    labels: Records[TrelloLabel] = Field(default_factory=list)
    members: Records[TrelloMember] = Field(default_factory=list)
    checklists: Records[TrelloChecklist] = Field(default_factory=list)
    actions: Records[TrelloAction] = Field(default_factory=list)
    # Every action in the source, comments or not; set by the compact form.
    action_total: int | None = Field(default=None, alias="actionTotal")

    def comments(self) -> list[TrelloAction]:
        """Comment actions on a card."""
        return [a for a in self.actions if a.type == TRELLO_COMMENT_ACTION and a.card_id]

    @property
    def action_count(self) -> int:
        """How many actions the source held."""
        return len(self.actions) if self.action_total is None else self.action_total

    @property
    def action_cap_hit(self) -> bool:
        """Whether the export is at the 1,000-action cap, so older comments are missing."""
        return self.action_count >= TRELLO_EXPORT_ACTION_CAP
