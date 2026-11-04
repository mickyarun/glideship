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

"""Running an AI draft with nothing to reach for, and leaving nothing behind.

The prompt holds people's work and words, and text other people typed, so
a run gets no built-in tools, no MCP servers and no repository. Its logs
carry no prompt or output, and the CLI's saved transcript is deleted
straight after. A provider that can't guarantee this is refused, and the
person gets the manual view.
"""

import contextlib
import os
import uuid
from pathlib import Path

from app.core.logging import content_free_logs
from app.services.ai_runner import run_agent_for_org_id
from app.services.claude_errors import ClaudeErrorCode
from app.services.claude_runner import NO_REPO_CONTEXT, ClaudeRunnerConfig, ClaudeRunResult

TIMEOUT_SECONDS = 240
# One reply, no tool loop.
MAX_TURNS = 1
# Retrying can't help until someone changes the setup: go to the manual view.
PERMANENT = frozenset(
    {ClaudeErrorCode.UNSUPPORTED, ClaudeErrorCode.BINARY_MISSING, ClaudeErrorCode.AUTH}
)


def forget_transcript(session_id: str) -> None:
    """Delete the transcript the CLI saved for this run, wherever it filed it."""
    root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    for path in root.glob(f"*/{session_id}.jsonl"):
        with contextlib.suppress(OSError):
            path.unlink()


async def run_draft(org_id: uuid.UUID, prompt: str) -> ClaudeRunResult:
    """One tool-less run for this org."""
    session_id = str(uuid.uuid4())
    config = ClaudeRunnerConfig(
        max_turns=MAX_TURNS,
        timeout_seconds=TIMEOUT_SECONDS,
        builtin_tools=[],
        no_mcp=True,
        cli_session_id=session_id,
    )
    with content_free_logs():
        try:
            return await run_agent_for_org_id(org_id, prompt, NO_REPO_CONTEXT, config)
        finally:
            forget_transcript(session_id)
