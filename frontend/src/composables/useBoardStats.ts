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

// What the board page counts: cards shown and open (and each column's
// count, of archived cards in that view), whether more pages
// wait, and the two board-wide states (a new board with no cards, and
// filters that match nothing, with a summary of what's set).

import { computed } from 'vue'
import type { BoardPage } from '@/composables/useBoardPage'
import { filterSummary, hasFilters } from '@/utils/boardFilters'

export function useBoardStats(page: BoardPage, nameFor: (userId: string) => string) {
  const { cards, board } = page
  const columns = computed(() => Object.values(cards.columns))
  const shownCount = computed(() => columns.value.reduce((n, c) => n + c.items.length, 0))
  const totalOpen = computed(() => Object.values(cards.counts).reduce((n, c) => n + c, 0))
  // The stage counts are of open cards; the archived view counts what it loaded.
  const columnCounts = computed<Record<string, number>>(() =>
    cards.filters.archived
      ? Object.fromEntries(Object.entries(cards.columns).map(([id, c]) => [id, c.items.length]))
      : cards.counts,
  )
  const hasMore = computed(() => columns.value.some(c => c.cursor !== null))
  const allLoaded = computed(() => columns.value.length > 0 && columns.value.every(c => c.loaded))
  const noMatch = computed(() => allLoaded.value && hasFilters(cards.filters) && shownCount.value === 0)
  const emptyBoard = computed(
    () =>
      !cards.filters.archived &&
      !hasFilters(cards.filters) &&
      totalOpen.value === 0 &&
      shownCount.value === 0 &&
      (allLoaded.value || !board.detail.value?.stages.length),
  )
  const repoName = (id: string) => page.repos.find(id)?.name ?? null
  const summary = computed(() => filterSummary(cards.filters, nameFor, board.detail.value?.labels ?? [], repoName))
  return { shownCount, totalOpen, columnCounts, hasMore, noMatch, emptyBoard, summary }
}
