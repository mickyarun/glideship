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

"""The fewest-goals setting: never above the most, and filled in for older settings."""

import pytest
from pydantic import ValidationError

from app.schemas.appraisal_settings import AppraisalSettings


def test_the_floor_defaults_to_three_and_may_equal_the_limit() -> None:
    assert AppraisalSettings().min_goals == 3
    assert AppraisalSettings(min_goals=5, max_goals=5).min_goals == 5


def test_the_floor_cannot_sit_above_the_limit() -> None:
    with pytest.raises(ValidationError, match="fewest goals"):
        AppraisalSettings(min_goals=4, max_goals=3)


def test_settings_saved_before_the_floor_get_three_or_their_limit() -> None:
    assert AppraisalSettings.model_validate({"max_goals": 8}).min_goals == 3
    assert AppraisalSettings.model_validate({"max_goals": 2}).min_goals == 2
