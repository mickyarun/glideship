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
// the server as text (a taken key or name reads the same either way); a
// taken one (BOARD_KEY_TAKEN) shows on the key field until the key changes.

import { computed, ref } from 'vue'
import { useBoardKeyFields } from '@/composables/useBoardKeyFields'
import { BoardCreateError, useBoardsStore } from '@/stores/boards'
import type { BoardDetail, BoardVisibility } from '@/types/boards'

export function useNewBoardForm() {
  const store = useBoardsStore()
  const fields = useBoardKeyFields()
  const { name, key, keyHint, keyLimits, setKey } = fields
  const template = ref('')
  const visibility = ref<BoardVisibility>('org')
  const saving = ref(false)
  const error = ref('')
  const loadError = ref('')
  const refusedKey = ref<{ key: string; message: string } | null>(null)
  const keyError = computed(() => (refusedKey.value?.key === key.value ? refusedKey.value.message : null))

  async function reset(): Promise<void> {
    fields.reset()
    visibility.value = 'org'
    error.value = ''
    loadError.value = ''
    refusedKey.value = null
    void store.ensureLimits()
    try {
      const templates = await store.ensureTemplates()
      if (!templates.some(t => t.id === template.value)) template.value = templates[0]?.id ?? ''
    } catch {
      loadError.value = "Couldn't load the board templates. Close this and try again."
    }
  }

  const canSubmit = computed(
    () => fields.complete.value && !!template.value && !saving.value && !keyError.value,
  )

  /** Create the board; resolves to it, or null with `error` set. */
  async function submit(): Promise<BoardDetail | null> {
    if (!canSubmit.value) return null
    saving.value = true
    error.value = ''
    refusedKey.value = null
    try {
      return await store.createBoard({
        name: name.value.trim(),
        key: key.value,
        template: template.value,
        visibility: visibility.value,
      })
    } catch (err) {
      const message = (err as Error).message
      if (err instanceof BoardCreateError && err.field === 'key') refusedKey.value = { key: key.value, message }
      else error.value = message
      return null
    } finally {
      saving.value = false
    }
  }

  return {
    name, key, keyHint, keyLimits, template, visibility, saving, error, loadError, keyError, canSubmit,
    setKey, reset, submit,
  }
}
