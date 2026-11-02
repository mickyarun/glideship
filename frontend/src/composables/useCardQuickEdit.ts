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

// Quick edits from a card on the board: who's on it and when it's due.
// Each shows at once and goes back if the server refuses it; only a card's
// latest edit may settle or undo it, so an older reply can't overwrite a
// newer pick. The people offered are those who can open the board (GET
// /boards/{key}/people: members, teams expanded, admins by permission, or
// the whole org for an org-wide board), plus anyone already assigned so
// they can be taken off (utils/boardPeople).

import { computed } from 'vue'
import { useBoardContext } from '@/composables/useBoardContext'
import { useMemberDirectory } from '@/composables/useMemberDirectory'
import { boardCardApi } from '@/services/boardCardApi'
import type { CardSummary, CardUpdate } from '@/types/boards'
import { locate, upsertCard } from '@/utils/boardColumns'
import { pickPeople, type PickPerson } from '@/utils/boardPeople'
import { extractApiError } from '@/utils/errors'

const OWN = { ignoreFilters: true }
const editSeq = new Map<string, number>()

export function useCardQuickEdit() {
  const { board, cards, people: boardPeople } = useBoardContext()
  const directory = useMemberDirectory()

  const canEdit = computed(() => board.can('edit_card'))

  /** Everyone who can be assigned, by name, with ``assigned`` kept in even if they lost access. */
  function people(assigned: string[]): PickPerson[] {
    return pickPeople(boardPeople.people.value, assigned, boardPeople.known.value, directory)
  }

  /** Save ``body``, showing ``guess`` meanwhile; resolves to the error, or null. */
  async function save(card: CardSummary, body: CardUpdate, guess: Partial<CardSummary>): Promise<string | null> {
    const seq = (editSeq.get(card.id) ?? 0) + 1
    editSeq.set(card.id, seq)
    const key = cards.boardKey
    const latest = () => editSeq.get(card.id) === seq && key === cards.boardKey
    const before = locate(cards.columns, card.id)?.card ?? card
    upsertCard(cards.columns, { ...before, ...guess }, cards.filters, OWN)
    try {
      const saved = await boardCardApi.update(key, card.number, body)
      if (latest()) upsertCard(cards.columns, saved, cards.filters, OWN)
      return null
    } catch (err) {
      if (latest()) upsertCard(cards.columns, before, cards.filters, OWN)
      return extractApiError(err, `Couldn't save ${card.key}. Try again.`)
    }
  }

  return { canEdit, people, save }
}
