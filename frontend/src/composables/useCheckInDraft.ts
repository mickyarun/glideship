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

import { onBeforeUnmount, reactive, ref, watch, type Ref } from 'vue'

import { useCheckInsStore } from '@/stores/checkIns'
import type { CheckInNote, CheckInRead } from '@/types/appraisal'

const DELAY_MS = 800

export type SaveState = 'saved' | 'saving' | 'unsaved' | 'failed'

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
  const state = ref<SaveState>('saved')
  const problem = ref('')
  let timer: ReturnType<typeof setTimeout> | undefined
  let loading = false

  watch(
    () => checkIn.value?.id,
    () => {
      clearTimeout(timer)
      loading = true
      Object.assign(draft, copy(checkIn.value?.note ?? draft))
      state.value = 'saved'
      loading = false
    },
    { immediate: true },
  )

  async function save(): Promise<void> {
    const id = checkIn.value?.id
    if (!id) return
    state.value = 'saving'
    problem.value = (await store.saveNote(id, copy(draft))) ?? ''
    state.value = problem.value ? 'failed' : 'saved'
  }

  watch(
    draft,
    () => {
      if (loading || !checkIn.value?.can_edit) return
      state.value = 'unsaved'
      clearTimeout(timer)
      timer = setTimeout(() => void save(), DELAY_MS)
    },
    { deep: true },
  )

  /** Save now, before sending; whether it saved. */
  async function flush(): Promise<boolean> {
    clearTimeout(timer)
    if (state.value === 'unsaved' || state.value === 'failed') await save()
    return state.value === 'saved'
  }

  onBeforeUnmount(() => {
    if (state.value === 'unsaved') void save()
    clearTimeout(timer)
  })

  return { draft, state, problem, flush }
}
