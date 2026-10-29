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

"""Board templates: YAML files in ``templates/``, validated on load.

A template names a board's starting stages and, optionally, the stage that
hands cards over to development and the stage a returned card lands in.
The file's stem is the template id (``content-seo.yaml`` → ``content-seo``).
"""

from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import settings
from app.models.board import STAGE_NAME_LENGTH
from app.models.board_enums import BoardStageCategory

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


class TemplateStage(BaseModel):
    """One starting stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=STAGE_NAME_LENGTH)
    category: BoardStageCategory
    default: bool = False
    wip_limit: int | None = Field(default=None, gt=0)


class BoardTemplate(BaseModel):
    """A validated board template."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    description: str = ""
    stages: tuple[TemplateStage, ...]
    handover_stage: str | None = None
    return_stage: str | None = None

    @model_validator(mode="after")
    def _check_stages(self) -> Self:
        """Enforce the same stage rules a board has."""
        limit = settings.boards.max_stages_per_board
        if len(self.stages) > limit:
            raise ValueError(f"a template has at most {limit} stages")
        names = [s.name for s in self.stages]
        if len(set(names)) != len(names):
            raise ValueError("stage names must be unique")
        categories = {s.category for s in self.stages}
        for needed in (BoardStageCategory.TODO, BoardStageCategory.DONE):
            if needed not in categories:
                raise ValueError(f"a template needs at least one {needed.value} stage")
        if sum(s.default for s in self.stages) != 1:
            raise ValueError("exactly one stage must be the default")
        self._check_named_stage(self.handover_stage, BoardStageCategory.DONE, "handover_stage")
        self._check_named_stage(self.return_stage, BoardStageCategory.TODO, "return_stage")
        if self.return_stage is not None and self.handover_stage is None:
            raise ValueError("return_stage needs a handover_stage")
        return self

    def _check_named_stage(
        self, name: str | None, category: BoardStageCategory, field: str
    ) -> None:
        if name is None:
            return
        stage = next((s for s in self.stages if s.name == name), None)
        if stage is None:
            raise ValueError(f"{field} {name!r} is not one of the stages")
        if stage.category is not category:
            raise ValueError(f"{field} must be a {category.value} stage")


def parse_template(raw: object) -> BoardTemplate:
    """Validate one template's parsed YAML."""
    return BoardTemplate.model_validate(raw)


@cache
def load_templates(directory: Path = TEMPLATES_DIR) -> MappingProxyType[str, BoardTemplate]:
    """Every template in ``directory``, keyed by file stem, in file-name order.

    Raises on the first invalid file; the unit tests load every shipped
    template, so a bad one fails CI rather than a board create.
    """
    templates = {
        path.stem: parse_template(yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in sorted(directory.glob("*.yaml"))
    }
    return MappingProxyType(templates)
