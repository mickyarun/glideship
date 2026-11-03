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

"""How a claimed daily DM ended, from what the Slack sender reported."""

from app.models.digest_claim import DigestClaimStatus


def claim_outcome(reached: bool | None) -> DigestClaimStatus:
    """Sent, failed (retried by a later tick), or skipped (no Slack, not linked, or muted).

    ``reached`` is the person's entry in what :func:`app.services.slack_dm.send_each`
    returned: None when they were left out.
    """
    if reached is None:
        return DigestClaimStatus.SKIPPED
    return DigestClaimStatus.SENT if reached else DigestClaimStatus.FAILED
