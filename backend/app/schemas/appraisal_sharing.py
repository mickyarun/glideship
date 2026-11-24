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

"""HR sending a review back, and the person's reply when they've read the result."""

from pydantic import BaseModel, Field, field_validator


class NoteBody(BaseModel):
    """HR's note when sending a review back; the manager reads it."""

    note: str = Field(min_length=1, max_length=600)

    @field_validator("note")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Say what to look at again.")
        return value


class ReplyBody(BaseModel):
    """The employee's optional reply when acknowledging; HR reads it too."""

    reply: str = Field("", max_length=1000)
