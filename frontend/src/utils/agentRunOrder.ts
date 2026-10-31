// Copyright 2025-2026 Arun Rajkumar
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// How far along a run is, so an update that arrives late (a Run reply
// saying "queued" after the board already heard it failed) never puts a
// run back a step. A run only moves forward: queued, then running, then
// ended; one that has finished beats one that hasn't.

import type { AgentRunRead, AgentRunStatus } from '@/types/boards'

const STATUS_RANK: Record<AgentRunStatus, number> = {
  pending: 0,
  running: 1,
  completed: 2,
  failed: 2,
  canceled: 2,
}

export type RunProgress = Pick<AgentRunRead, 'status' | 'finished_at'>

/** ``next`` is less far along than ``held`` (the same run), so it's stale. */
export function isBehind(next: RunProgress, held: RunProgress): boolean {
  return STATUS_RANK[next.status] < STATUS_RANK[held.status] || (!next.finished_at && !!held.finished_at)
}
