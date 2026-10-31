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

"""Import sources by kind. A new source adds an enum value and one entry here."""

from collections.abc import Callable
from types import MappingProxyType
from typing import Final

from app.models.external_import import ImportSourceKind
from app.services.imports.source import ImportSource
from app.services.imports.trello.source import TrelloSource

SOURCES: Final[MappingProxyType[ImportSourceKind, Callable[[], ImportSource]]] = MappingProxyType(
    {ImportSourceKind.TRELLO: TrelloSource}
)


def source_for(kind: ImportSourceKind) -> ImportSource:
    """A fresh source for one job (sources cache what they load)."""
    return SOURCES[kind]()
