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

"""Why an appraisal action was refused, independent of HTTP.

Services raise these; :mod:`app.api.v1._appraisal_errors` maps each kind to
a status code. There is no "forbidden": a record the caller may not see
answers "not found", so its existence isn't revealed.
"""


class AppraisalError(Exception):
    """An appraisal rule refused the action; ``str(exc)`` is safe to show."""


class AppraisalNotFoundError(AppraisalError):
    """It doesn't exist, or the caller may not see it."""


class AppraisalConflictError(AppraisalError):
    """The current state doesn't allow it (cycle running, check-in closed, ...)."""


class AppraisalInvalidError(AppraisalError):
    """The input doesn't make sense (cadences that don't fit, bad dates, ...)."""
