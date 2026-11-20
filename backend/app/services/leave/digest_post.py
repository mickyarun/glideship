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

"""Sending one who's-out message to every configured channel."""

from app.services.slack_interactive import post_message


async def post_to_channels(token: str, channel_ids: list[str], text: str) -> list[str]:
    """Post ``text`` to each channel; the Slack error code of each one that failed.

    One channel the bot isn't in must not stop the others, so every channel
    is tried. An empty result means all of them got it.
    """
    errors = []
    for channel_id in channel_ids:
        _channel, _ts, error = await post_message(token, channel_id, text)
        if error:
            errors.append(error)
    return errors
