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
// here and builds the mapping; the server checks the rest, and a refusal
// about one field (a taken key, a stage name the board has) shows on it
// until that field changes.

import { computed, ref, watch, type Ref } from 'vue'
import { useBoardKeyFields } from '@/composables/useBoardKeyFields'
import type {
  ArchivedChoice, BoardVisibility, ImportDiscovery, ImportSessionRead, ImportTarget,
} from '@/types/boards'
import {
  fieldRefusals, newStageNames, rowProblems, stageCountProblem, type StageCheckLimits,
} from '@/utils/importChecks'
import type { ImportFailure } from '@/utils/importErrors'
import {
  buildMapping, cardsToImport, listRows, personRows, type ListRow, type PersonRow, type StageOption,
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
    stages: Ref<StageOption[]>
    people: Ref<PickablePerson[] | null>
    limits: Ref<StageCheckLimits>
  },
) {
  const rows = ref<ListRow[]>([])
  const people = ref<PersonRow[]>([])
  const archived = ref<ArchivedChoice>('skip')
  const board = useBoardKeyFields()
  const visibility = ref<BoardVisibility>('org')
  // A refusal holds the value it was about, so editing the field clears it.
  const refusedKey = ref<{ key: string; message: string } | null>(null)
  const refusedRows = ref<Record<string, { name: string; message: string }>>({})
  let filledFor: string | null = null

  const discovery = computed<ImportDiscovery | null>(() => session.value?.discovery ?? null)

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
  const keyError = computed(() =>
    refusedKey.value && refusedKey.value.key === board.key.value ? refusedKey.value.message : null,
  )
  const problems = computed(() => {
    const local = rowProblems(rows.value, options.stages.value, options.limits.value)
    return rows.value.map((r, i) => {
      const refused = refusedRows.value[r.list.id]
      return local[i] ?? (refused && refused.name === r.name.trim() && r.choice === 'new' ? refused.message : null)
    })
  })
  const stageProblem = computed(() =>
    stageCountProblem(rows.value, options.stages.value.length, options.limits.value.maxStages),
  )
  const target = computed<ImportTarget>(() =>
    options.existingKey.value
      ? { kind: 'existing', key: options.existingKey.value }
      : { kind: 'new', name: board.name.value.trim(), key: board.key.value, visibility: visibility.value },
  )
  // An import with no cards still makes sense when it creates stages.
  const somethingToImport = computed(() => counts.value.cards > 0 || newStageNames(rows.value).size > 0)
  const valid = computed(
    () =>
      problems.value.every(p => !p) &&
      !stageProblem.value &&
      !keyError.value &&
      (!!options.existingKey.value || board.complete.value) &&
      somethingToImport.value,
  )

  function pick(row: PersonRow, userId: string | null): void {
    row.userId = userId
    row.confirmed = true
  }

  /** Put a refused review's message on the field it's about, if it's about one. */
  function showRefusal(failure: ImportFailure | null): void {
    const found = fieldRefusals(failure, !options.existingKey.value, rows.value)
    refusedKey.value = found.key ? { key: board.key.value, message: found.key } : null
    refusedRows.value = Object.fromEntries(
      rows.value.filter(r => found.rows[r.list.id]).map(r => [r.list.id, { name: r.name.trim(), message: found.rows[r.list.id]! }]),
    )
  }

  const mapping = () => buildMapping(target.value, rows.value, people.value, archived.value)

  return {
    rows, people, archived, board, visibility, discovery, counts, problems, stageProblem, keyError,
    valid, pick, mapping, showRefusal,
  }
}

export type ImportMappingForm = ReturnType<typeof useImportMappingForm>
