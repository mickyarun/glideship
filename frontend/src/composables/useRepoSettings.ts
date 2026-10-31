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

// A board's linked repositories as its settings edit them: the org's
// active repositories to pick from (admins only), link one, unlink one.
// Each reply is the board's new list, which goes straight into the board
// context (this tab skips its own repos_changed echo); an unlink also
// clears the repository from the loaded cards and from the filter.
// ``cardsNaming`` counts the open cards naming a repository when the
// board's loaded cards are all of them (no filter, every page in), else
// null, so an unlink can say what it clears without a request.

import { computed, ref } from 'vue'
import type { BoardPage } from '@/composables/useBoardPage'
import type { BoardSettingsStatus } from '@/composables/useBoardSettingsStatus'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import type { BoardRepoRead, RepoOption } from '@/types/boards'
import { hasFilters } from '@/utils/boardFilters'
import { extractApiError } from '@/utils/errors'

export function useRepoSettings(page: BoardPage, status: BoardSettingsStatus) {
  const options = ref<RepoOption[]>([])
  const optionsError = ref('')
  const loadingOptions = ref(false)
  /** The org's list came back at least once. */
  const optionsLoaded = ref(false)
  const linked = computed(() => page.repos.repos.value)

  async function loadOptions(): Promise<void> {
    const key = page.board.detail.value?.board.key
    if (!key) return
    loadingOptions.value = true
    optionsError.value = ''
    try {
      options.value = (await boardSettingsApi.repoOptions(key)).items
      optionsLoaded.value = true
    } catch (err) {
      optionsError.value = extractApiError(err, "Couldn't load the org's repositories.")
    } finally {
      loadingOptions.value = false
    }
  }

  function mark(repoId: string, isLinked: boolean): void {
    options.value = options.value.map(o => (o.id === repoId ? { ...o, linked: isLinked } : o))
  }

  function link(repo: BoardRepoRead): Promise<boolean> {
    return status.run(
      async key => {
        page.repos.set((await boardSettingsApi.linkRepo(key, repo.id)).items)
        mark(repo.id, true)
      },
      `Linked ${repo.name}`,
      { refresh: false, fallback: "Couldn't link that repository. Try again." },
    )
  }

  function unlink(repo: BoardRepoRead): Promise<boolean> {
    return status.run(
      async key => {
        page.repos.set((await boardSettingsApi.unlinkRepo(key, repo.id)).items)
        page.forgetRepo(repo.id)
        mark(repo.id, false)
      },
      `Unlinked ${repo.name}`,
      { refresh: false, fallback: "Couldn't unlink that repository. Try again." },
    )
  }

  function cardsNaming(repoId: string): number | null {
    const { cards } = page
    const columns = Object.values(cards.columns)
    const complete = !hasFilters(cards.filters) && !cards.filters.archived
      && columns.every(c => c.loaded && !c.cursor)
    if (!complete || !columns.length) return null
    return columns.reduce((n, c) => n + c.items.filter(card => card.repo_id === repoId).length, 0)
  }

  return { options, optionsError, loadingOptions, optionsLoaded, linked, loadOptions, link, unlink, cardsNaming }
}
