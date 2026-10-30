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

// The new-board dialog's form: the key follows the name until someone
// edits it, the first template is picked, and the board is created with
// org visibility unless they choose members-only. Errors come back from
// the server as text (a taken key or name reads the same either way).

import { computed, ref, watch } from 'vue'
import { useBoardsStore } from '@/stores/boards'
import type { BoardDetail, BoardVisibility } from '@/types/boards'
import { normaliseKey, suggestKey } from '@/utils/boardIndex'

export function useNewBoardForm() {
  const store = useBoardsStore()
  const name = ref('')
  const key = ref('')
  const keyEdited = ref(false)
  const template = ref('')
  const visibility = ref<BoardVisibility>('org')
  const saving = ref(false)
  const error = ref('')
  const loadError = ref('')

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

  async function reset(): Promise<void> {
    name.value = ''
    key.value = ''
    keyEdited.value = false
    visibility.value = 'org'
    error.value = ''
    loadError.value = ''
    void store.ensureLimits()
    try {
      const templates = await store.ensureTemplates()
      if (!templates.some(t => t.id === template.value)) template.value = templates[0]?.id ?? ''
    } catch {
      loadError.value = "Couldn't load the board templates. Close this and try again."
    }
  }

  const canSubmit = computed(
    () =>
      !!name.value.trim() &&
      key.value.length >= (keyLimits.value?.min ?? 1) &&
      !!template.value &&
      !saving.value,
  )

  /** Create the board; resolves to it, or null with `error` set. */
  async function submit(): Promise<BoardDetail | null> {
    if (!canSubmit.value) return null
    saving.value = true
    error.value = ''
    try {
      return await store.createBoard({
        name: name.value.trim(),
        key: key.value,
        template: template.value,
        visibility: visibility.value,
      })
    } catch (err) {
      error.value = (err as Error).message
      return null
    } finally {
      saving.value = false
    }
  }

  return {
    name, key, keyHint, keyLimits, template, visibility, saving, error, loadError, canSubmit,
    setKey, reset, submit,
  }
}
