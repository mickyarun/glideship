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

// The review step's form: each Trello list's stage, each member's person,
// archived cards, and (for a new board) its name, key and visibility. It
// fills from the parse (or the mapping saved before), checks what it can
// here and builds the mapping; the server checks the rest and its answer
// is shown as it comes (a stage name the board already has, a taken key).

import { computed, ref, watch, type Ref } from 'vue'
import { useBoardKeyFields } from '@/composables/useBoardKeyFields'
import type {
  ArchivedChoice, BoardVisibility, ImportSessionRead, ImportTarget, TrelloDiscovery,
} from '@/types/boards'
import {
  buildMapping, cardsToImport, listRows, personRows, rowProblem, type ListRow, type PersonRow,
} from '@/utils/importMapping'

export interface PickablePerson {
  id: string
  name: string
}

export function useImportMappingForm(
  session: Ref<ImportSessionRead | null>,
  options: {
    existingKey: Ref<string | null>
    /** The existing board's stages (none for a new board). */
    stages: Ref<{ id: string; name: string }[]>
    people: Ref<PickablePerson[] | null>
    stageNameMax: Ref<number | null>
  },
) {
  const rows = ref<ListRow[]>([])
  const people = ref<PersonRow[]>([])
  const archived = ref<ArchivedChoice>('skip')
  const board = useBoardKeyFields()
  const visibility = ref<BoardVisibility>('org')
  let filledFor: string | null = null

  const discovery = computed<TrelloDiscovery | null>(() => session.value?.discovery ?? null)

  function fill(): void {
    const s = session.value
    const found = discovery.value
    if (!s || !found || filledFor === s.id) return
    filledFor = s.id
    const saved = s.mapping
    rows.value = listRows(found, saved, options.stages.value)
    archived.value = saved?.archived_cards ?? 'skip'
    const allowed = options.people.value ? new Set(options.people.value.map(p => p.id)) : null
    people.value = personRows(found, saved, allowed)
    const target = saved?.target
    board.reset(target?.kind === 'new' ? target.name : found.board_name)
    if (target?.kind === 'new') {
      board.setKey(target.key)
      visibility.value = target.visibility
    }
  }

  watch([session, options.people], fill, { immediate: true })
  // People who can't open the target never stay suggested once the list is known.
  watch(options.people, list => {
    if (!list) return
    const allowed = new Set(list.map(p => p.id))
    for (const row of people.value) {
      if (row.userId && !row.confirmed && !allowed.has(row.userId)) row.userId = null
    }
  })

  const counts = computed(() =>
    discovery.value ? cardsToImport(discovery.value, rows.value, archived.value) : { cards: 0, archived: 0 },
  )
  const problems = computed(() => rows.value.map(r => rowProblem(r, options.stageNameMax.value)))
  const target = computed<ImportTarget>(() =>
    options.existingKey.value
      ? { kind: 'existing', key: options.existingKey.value }
      : { kind: 'new', name: board.name.value.trim(), key: board.key.value, visibility: visibility.value },
  )
  const valid = computed(
    () =>
      problems.value.every(p => !p) &&
      (!!options.existingKey.value || board.complete.value) &&
      counts.value.cards > 0,
  )

  function pick(row: PersonRow, userId: string | null): void {
    row.userId = userId
    row.confirmed = true
  }

  const mapping = () => buildMapping(target.value, rows.value, people.value, archived.value)

  return { rows, people, archived, board, visibility, discovery, counts, problems, valid, pick, mapping }
}

export type ImportMappingForm = ReturnType<typeof useImportMappingForm>
