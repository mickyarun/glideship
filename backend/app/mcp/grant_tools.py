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

"""What a scoped token's tool list shows: only its tools, and only its repositories.

A grant with ``repos`` narrows each code tool's ``repo_id`` to an ``enum`` of
those repositories' ids (named in the description), so the agent is offered
nothing it would be refused.
"""

import copy
from typing import Any

from app.mcp.token_grants import REPO_ID_PARAM, REPO_SCOPED_TOOLS, InternalTokenGrant


def scoped_input_schema(
    tool_name: str, schema: dict[str, Any], grant: InternalTokenGrant | None
) -> dict[str, Any]:
    """``schema`` as ``grant`` lets the tool be called (unchanged without a repo limit)."""
    if grant is None or grant.repos is None or tool_name not in REPO_SCOPED_TOOLS:
        return schema
    scoped = copy.deepcopy(schema)
    names = ", ".join(f"{r.name}={r.id}" for r in grant.repos) or "none"
    scoped.setdefault("properties", {})[REPO_ID_PARAM] = {
        "type": "string",
        "enum": [str(r.id) for r in grant.repos],
        "description": f"One of this run's repositories: {names}.",
    }
    return scoped


def visible(tool_name: str, grant: InternalTokenGrant | None) -> bool:
    """Whether a tool list shown to ``grant``'s token includes ``tool_name``."""
    return grant is None or grant.allows(tool_name)
