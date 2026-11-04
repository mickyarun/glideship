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
carry no free text, and the CLI's saved transcript is deleted straight
after; one left by a crash goes at the next start. A provider that can't
guarantee this is refused, and the person gets the manual view.
"""

import contextlib
import shutil
import tempfile
import uuid
from pathlib import Path

from app.core.logging import content_free_logs
from app.services.ai_runner import run_agent_for_org_id
from app.services.claude_errors import ClaudeErrorCode
from app.services.claude_runner import (
    NO_REPO_CONTEXT,
    PRIVATE_RUN_DIR_PREFIX,
    ClaudeRunnerConfig,
    ClaudeRunResult,
)

TIMEOUT_SECONDS = 240
# One reply, no tool loop.
MAX_TURNS = 1
# Retrying can't help until someone changes the setup: go to the manual view.
PERMANENT = frozenset(
    {ClaudeErrorCode.UNSUPPORTED, ClaudeErrorCode.BINARY_MISSING, ClaudeErrorCode.AUTH}
)


def _projects() -> Path:
    # The child's env filter drops CLAUDE_CONFIG_DIR, so this is where it writes.
    return Path.home() / ".claude" / "projects"


def forget_transcript(session_id: str) -> None:
    """Delete the transcript the CLI saved for this run, wherever it filed it."""
    for path in _projects().glob(f"*/{session_id}.jsonl"):
        with contextlib.suppress(OSError):
            path.unlink()
            path.parent.rmdir()  # Only goes if empty: a private run's own folder.


def sweep_leftovers() -> None:
    """Remove what a crashed run left: its transcript folder and throwaway directory.

    Call before any run starts. Folder names are the run's path with
    punctuation as dashes, so the prefix survives in them.
    """
    prefix = PRIVATE_RUN_DIR_PREFIX.rstrip("-")
    for path in _projects().glob(f"*{prefix}-*"):
        shutil.rmtree(path, ignore_errors=True)
    for path in Path(tempfile.gettempdir()).glob(f"{PRIVATE_RUN_DIR_PREFIX}*"):
        shutil.rmtree(path, ignore_errors=True)


async def run_draft(org_id: uuid.UUID, prompt: str) -> ClaudeRunResult:
    """One tool-less run for this org."""
    session_id = str(uuid.uuid4())
    config = ClaudeRunnerConfig(
        max_turns=MAX_TURNS,
        timeout_seconds=TIMEOUT_SECONDS,
        builtin_tools=[],
        private_run=True,
        cli_session_id=session_id,
    )
    with content_free_logs():
        try:
            return await run_agent_for_org_id(org_id, prompt, NO_REPO_CONTEXT, config)
        finally:
            forget_transcript(session_id)
