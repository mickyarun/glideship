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

// Everyone who can open the open board (GET /boards/{key}/people): their
// own role, a team's, boards:manage, or an org-wide board. Exactly the set
// a card can be assigned to, so every assignee picker and the assignee
// filter read it from here. Loaded once per board by useBoardPage and
// shared through the board context; a member change, people_changed and a
// resync reload it.

import { computed, ref } from 'vue'
import { boardsApi } from '@/services/boardsApi'
import type { BoardPersonRead } from '@/types/boards'
import { logFailure } from '@/utils/logFailure'

export function useBoardPeople() {
  const people = ref<BoardPersonRead[]>([])
  const loaded = ref(false)
  /** The last fetch failed, so the list may be stale (or empty). */
  const failed = ref(false)
  let seq = 0

  const byId = computed(() => new Map(people.value.map(p => [p.id, p])))

  /** Load the board's people; a reply for an older call (or board) is dropped. */
  async function load(key: string, current: () => boolean = () => true): Promise<void> {
    const mine = ++seq
    try {
      const reply = await boardsApi.people(key)
      if (mine !== seq || !current()) return
      people.value = [...reply.items].sort((a, b) => a.name.localeCompare(b.name))
      loaded.value = true
      failed.value = false
    } catch (err) {
      if (mine === seq) failed.value = true
      logFailure('boards', 'people fetch', err)
    }
  }

  function reset(): void {
    seq++
    people.value = []
    loaded.value = false
    failed.value = false
  }

  const find = (id: string) => byId.value.get(id) ?? null
  /** Loaded, and the last fetch worked: someone missing from it really has no access. */
  const known = computed(() => loaded.value && !failed.value)

  return { people, loaded, failed, known, byId, load, reset, find }
}

export type BoardPeople = ReturnType<typeof useBoardPeople>
