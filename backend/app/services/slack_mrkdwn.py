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

"""Making user-supplied text safe inside a Slack message (pure, no I/O)."""


def escape_mrkdwn(text: str) -> str:
    """Neutralise Slack's control characters in user-supplied text.

    Slack parses ``<!channel>``, ``<@U123>`` and ``<url|label>`` in both
    ``mrkdwn`` blocks and the top-level ``text``. A name containing them
    would ping the channel or render a disguised link, so ``& < >`` are
    escaped exactly as Slack's formatting guide prescribes.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
