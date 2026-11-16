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

"""One reminder DM and what it announces, shared by every reminder stream."""

import uuid
from dataclasses import dataclass, field


@dataclass
class Message:
    """One person's DM of one kind, and what it announces once delivered."""

    text: str
    check_ins: list[uuid.UUID] = field(default_factory=list)
    feedback: list[uuid.UUID] = field(default_factory=list)
    appraisals: list[uuid.UUID] = field(default_factory=list)


Outbox = dict[uuid.UUID, Message]
