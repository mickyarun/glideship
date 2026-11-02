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

"""Trello as an import source: an uploaded JSON export, or the REST API.

Both modes end in the same stored board JSON, so parsing, the review
screen and the import job are shared; only fetching differs. Upload mode
never fetches a URL found in the file: attachments become links. API mode
downloads files only from ``api.trello.com`` attachment endpoints.
"""
