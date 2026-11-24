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

/**
 * The person's words on a check-in, saved as they type.
 *
 * Holds a copy of the note, saves it a moment after the last change, and
 * says where the save is. The copy follows the check-in only when another
 * check-in opens, so a save coming back never wipes what is being typed.
 */

import { reactive, watch, type Ref } from 'vue'

import { useAutosave } from '@/composables/useAutosave'
import { useCheckInsStore } from '@/stores/checkIns'
import type { CheckInNote, CheckInRead } from '@/types/appraisal'

export type { SaveState } from '@/composables/useAutosave'

function copy(note: CheckInNote): CheckInNote {
  return {
    lines: { ...note.lines },
    went_well: note.went_well ?? '',
    item_notes: { ...(note.item_notes ?? {}) },
    blocking: note.blocking,
    next_month: note.next_month,
  }
}

export function useCheckInDraft(checkIn: Ref<CheckInRead | null>) {
  const store = useCheckInsStore()
  const draft = reactive<CheckInNote>({ lines: {}, went_well: '', item_notes: {}, blocking: '', next_month: '' })
  const { state, problem, reset, flush } = useAutosave(
    () => JSON.stringify(draft),
    async () => (checkIn.value ? store.saveNote(checkIn.value.id, copy(draft)) : null),
    () => Boolean(checkIn.value?.can_edit),
  )

  watch(
    () => checkIn.value?.id,
    () => {
      Object.assign(draft, copy(checkIn.value?.note ?? draft))
      reset()
    },
    { immediate: true },
  )

  return { draft, state, problem, flush }
}
