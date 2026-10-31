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

// The repositories the open board links (GET /boards/{key}/repos), loaded
// once per board by useBoardPage and shared through the board context, so
// a card's repository chip, its picker and the Repository filter read one
// list. The board's live channel keeps it current (repos_changed): a link
// arrives with the repository, an unlink by id.

import { computed, ref } from 'vue'
import { boardsApi } from '@/services/boardsApi'
import type { BoardRepoRead } from '@/types/boards'
import { logFailure } from '@/utils/logFailure'

const byName = (a: BoardRepoRead, b: BoardRepoRead) => a.name.localeCompare(b.name)

export function useBoardRepos() {
  const repos = ref<BoardRepoRead[]>([])
  let seq = 0

  const byId = computed(() => new Map(repos.value.map(r => [r.id, r])))

  async function load(key: string, current: () => boolean = () => true): Promise<void> {
    const mine = ++seq
    try {
      const reply = await boardsApi.repos(key)
      if (mine === seq && current()) set(reply.items)
    } catch (err) {
      logFailure('boards', 'repos fetch', err)
    }
  }

  function reset(): void {
    seq++
    repos.value = []
  }

  /** The whole list, as a link or unlink reply returns it. */
  function set(items: BoardRepoRead[]): void {
    repos.value = [...items].sort(byName)
  }

  function linked(repo: BoardRepoRead): void {
    set([...repos.value.filter(r => r.id !== repo.id), repo])
  }

  function unlinked(repoId: string): void {
    repos.value = repos.value.filter(r => r.id !== repoId)
  }

  /** A linked repository, or null (none set, or one this tab doesn't know yet). */
  const find = (id: string | null) => (id ? byId.value.get(id) ?? null : null)

  return { repos, byId, load, reset, set, linked, unlinked, find }
}

export type BoardRepos = ReturnType<typeof useBoardRepos>
