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

"""The Delivery (BUD) board's settings, stored under ``organizations.config["delivery"]``."""

from pydantic import BaseModel, ConfigDict


class DeliverySettings(BaseModel):
    """Delivery board settings; a missing section reads as the defaults.

    ``ai_enabled`` is Delivery's AI switch: when off, no BUD stage agent
    starts (``create_agent_task_for_stage``); when on, each BUD's own
    ``auto_generate_phases`` still decides per phase.
    """

    ai_enabled: bool = True


class DeliverySettingsUpdate(BaseModel):
    """A change to the Delivery settings; omitted fields stay as they are."""

    model_config = ConfigDict(extra="forbid")

    ai_enabled: bool | None = None
