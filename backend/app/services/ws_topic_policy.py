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

"""Which WebSocket topics a connection may subscribe to.

Default-deny: a topic is allowed only if its prefix is listed here. Each
prefix declares who may read it:

* ``user`` — the second segment must be the caller's own user id.
* ``org`` — the second segment must be the caller's own org id.
* ``bud`` — the second segment is a BUD id, which must belong to the
  caller's org. BUD ids appear in URLs and Slack links, so they are not a
  secret; the WebSocket handler checks ownership via :func:`bud_id_of`.
* ``board`` — the second segment is a board id; the WebSocket handler
  checks the caller holds a role on that board via :func:`board_id_of`.
* ``id`` — addressed by a server-minted UUID (a job or scan) that is only
  ever handed to the requester. The UUID is the capability.

``engineering`` marks topics that carry engineering-workspace data and so
need ``workspace:engineering``. Adding a new publisher means adding its
prefix here, or no client will ever receive it.

Scopes in :data:`REVOCABLE_SCOPES` can lose access while a socket is open
(a board member is removed). Services publish a re-check on the topic's
:func:`access_topic`, or on :func:`people_access_topic` when a person's
access may have changed everywhere (a role change, a deactivation). No
client can subscribe to either; ``api/v1/ws_revocation.py`` handles them.
"""

from dataclasses import dataclass
from typing import Literal, assert_never

Scope = Literal["user", "org", "bud", "board", "id"]


@dataclass(frozen=True)
class TopicRule:
    """Access rule for one topic prefix."""

    scope: Scope
    engineering: bool


# Control topics: ``access:<topic>`` asks sockets holding ``<topic>`` to
# re-check it, and ``access:people:<org_id>`` asks for a re-check of some
# people's every revocable topic. The prefix is not in ``TOPIC_RULES``, so
# clients can't join either.
ACCESS_TOPIC_PREFIX = "access"
PEOPLE_ACCESS_SEGMENT = "people"
REVOCABLE_SCOPES: frozenset[Scope] = frozenset({"board"})
# Set on an event published with an access change: the user ids whose access
# changed, or None for everyone. Sockets named confirm access before
# forwarding it, and the key itself is never sent to clients.
ACCESS_CHANGED_KEY = "access_changed_for"

TOPIC_RULES: dict[str, TopicRule] = {
    "notifications": TopicRule(scope="user", engineering=False),
    "org": TopicRule(scope="org", engineering=False),
    "xp": TopicRule(scope="user", engineering=True),
    "yield_offer": TopicRule(scope="user", engineering=True),
    "quiz": TopicRule(scope="org", engineering=True),
    "agent_activity": TopicRule(scope="org", engineering=True),
    "job": TopicRule(scope="id", engineering=True),
    "scan": TopicRule(scope="id", engineering=True),
    "scan_synthesis_tool": TopicRule(scope="id", engineering=True),
    "todo": TopicRule(scope="bud", engineering=True),
    "bud": TopicRule(scope="bud", engineering=True),
    "board": TopicRule(scope="board", engineering=False),
}


@dataclass(frozen=True)
class Subscriber:
    """Identity of a WebSocket connection, resolved once at connect.

    ``permissions`` holds the caller's org permission ids; the org owner's
    set is every permission.
    """

    user_id: str
    org_id: str
    has_engineering: bool
    permissions: frozenset[str] = frozenset()

    def has(self, permission: str) -> bool:
        """Return True if the caller holds ``permission``."""
        return permission in self.permissions


def may_subscribe(topic: str, who: Subscriber) -> bool:
    """Return True if ``who`` may subscribe to ``topic``."""
    prefix, _, rest = topic.partition(":")
    rule = TOPIC_RULES.get(prefix)
    if rule is None or not rest:
        return False
    if rule.engineering and not who.has_engineering:
        return False
    owner = rest.split(":", 1)[0]
    match rule.scope:
        case "user":
            return owner == who.user_id
        case "org":
            return owner == who.org_id
        case "bud" | "board" | "id":
            # Decided by the scope's database check, or (``id``) by the
            # unguessable id itself.
            return True
        case _:
            assert_never(rule.scope)


def scope_of(topic: str) -> Scope | None:
    """The scope of a topic's prefix, or None for an unknown prefix."""
    rule = TOPIC_RULES.get(topic.partition(":")[0])
    return None if rule is None else rule.scope


def _id_in_scope(topic: str, scope: Scope) -> str | None:
    prefix, _, rest = topic.partition(":")
    rule = TOPIC_RULES.get(prefix)
    if rule is None or rule.scope != scope or not rest:
        return None
    return rest.split(":", 1)[0]


def bud_id_of(topic: str) -> str | None:
    """The BUD id a ``bud``-scoped topic names, for the ownership check."""
    return _id_in_scope(topic, "bud")


def board_id_of(topic: str) -> str | None:
    """The board id a ``board``-scoped topic names, for the role check."""
    return _id_in_scope(topic, "board")


def access_topic(topic: str) -> str | None:
    """The control topic that re-checks ``topic``, when its scope can be revoked."""
    scope = scope_of(topic)
    if scope is None or scope not in REVOCABLE_SCOPES:
        return None
    return f"{ACCESS_TOPIC_PREFIX}:{topic}"


def people_access_topic(org_id: str) -> str:
    """The control topic that re-checks people's revocable topics in one org."""
    return f"{ACCESS_TOPIC_PREFIX}:{PEOPLE_ACCESS_SEGMENT}:{org_id}"
