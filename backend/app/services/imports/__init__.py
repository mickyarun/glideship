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

"""Imports from other tools into boards.

A source (Trello first) implements :class:`app.services.imports.source.ImportSource`
and turns its data into card drafts and labels; the shared pipeline runs
discovery, plans the board, then writes the drafts in batches under a
silent :class:`app.services.imports.context.ImportContext`, recording each
item in ``external_item_maps`` so a re-import skips what's already there.
"""
