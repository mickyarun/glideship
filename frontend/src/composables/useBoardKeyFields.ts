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

// A new board's name and key, within the server's limits: the key follows
// the name until someone edits it, and the hint says what it will do.
// Shared by the New board dialog and an import into a new board.

import { computed, ref, watch } from 'vue'
import { useBoardsStore } from '@/stores/boards'
import { normaliseKey, suggestKey } from '@/utils/boardIndex'

export function useBoardKeyFields() {
  const store = useBoardsStore()
  const name = ref('')
  const key = ref('')
  const keyEdited = ref(false)

  const keyLimits = computed(() =>
    store.limits ? { min: store.limits.board_key_min, max: store.limits.board_key_max } : null,
  )

  watch(name, value => {
    if (!keyEdited.value) key.value = suggestKey(value, keyLimits.value)
  })

  function setKey(raw: string | null): void {
    keyEdited.value = true
    key.value = normaliseKey(raw ?? '', keyLimits.value?.max ?? null)
  }

  /** "Cards will be EVT-1, EVT-2…", or what the key still needs. */
  const keyHint = computed(() => {
    const min = keyLimits.value?.min ?? 1
    if (key.value.length < min) return `Letters only, at least ${min}. Cards are numbered from it.`
    return `Cards will be ${key.value}-1, ${key.value}-2… Can't be changed later.`
  })

  const complete = computed(() => !!name.value.trim() && key.value.length >= (keyLimits.value?.min ?? 1))

  /** Start again; the name defaults to `initial` (the key follows it). */
  function reset(initial = ''): void {
    keyEdited.value = false
    name.value = initial
    key.value = suggestKey(initial, keyLimits.value)
  }

  return { name, key, keyLimits, keyHint, complete, setKey, reset }
}

export type BoardKeyFields = ReturnType<typeof useBoardKeyFields>
