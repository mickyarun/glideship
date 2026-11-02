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

"""The rows a card run touches, as the job and the paths that end a run see them."""

from dataclasses import dataclass

from app.models.agent_skill import AgentSkill
from app.models.board import Board
from app.models.board_agent import BoardCardAgentRun
from app.models.board_card import BoardCard


@dataclass(frozen=True)
class RunRow:
    """A run with its card and board, and its skill unless that was deleted."""

    board: Board
    card: BoardCard
    run: BoardCardAgentRun
    skill: AgentSkill | None


@dataclass(frozen=True)
class RunRefs:
    """A run whose skill is still in the library: everything its job needs."""

    board: Board
    card: BoardCard
    run: BoardCardAgentRun
    skill: AgentSkill

    @property
    def row(self) -> RunRow:
        """The same rows, as the paths that end a run take them."""
        return RunRow(board=self.board, card=self.card, run=self.run, skill=self.skill)
