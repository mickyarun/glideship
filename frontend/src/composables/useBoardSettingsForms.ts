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

// The two board settings saved with the Save button: General (name and
// description) and Handover. Each is a draft of the open board's values;
// saving sends only what the form owns and puts the reply on the board.

import { computed, type Ref } from 'vue'
import type { BoardPage } from '@/composables/useBoardPage'
import type { BoardSettingsStatus } from '@/composables/useBoardSettingsStatus'
import { useSettingsDraft } from '@/composables/useSettingsDraft'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { useBoardsStore } from '@/stores/boards'
import type { BoardLimits } from '@/types/boards'
import type { BoardUpdate, HandoverTarget } from '@/types/boards/settings'

function tooLong(text: string, max: number | undefined, what: string): string {
  return max && text.length > max ? `Keep the ${what} to ${max} characters.` : ''
}

export function useGeneralForm(page: BoardPage, status: BoardSettingsStatus, limits: Ref<BoardLimits | null>) {
  const boards = useBoardsStore()
  const board = computed(() => page.board.detail.value?.board ?? null)
  const form = useSettingsDraft(() =>
    board.value ? { name: board.value.name, description: board.value.description ?? '' } : null,
  )

  const nameError = computed(() => {
    const name = form.draft.value?.name.trim() ?? ''
    return name ? tooLong(name, limits.value?.board_name_max, 'name') : 'Give the board a name.'
  })
  const descriptionError = computed(() =>
    tooLong(form.draft.value?.description ?? '', limits.value?.board_description_max, 'description'),
  )
  const valid = computed(() => form.dirty.value && !nameError.value && !descriptionError.value)

  async function save(): Promise<boolean> {
    if (!board.value || !valid.value) return false
    const changed = form.changes()
    const body: BoardUpdate = {}
    if (changed.name !== undefined && changed.name.trim() !== board.value.name) body.name = changed.name.trim()
    if (changed.description !== undefined) body.description = changed.description.trim() || null
    if (!Object.keys(body).length) {
      form.reset()
      return true
    }
    return status.run(async key => {
      page.board.detail.value = await boardSettingsApi.update(key, body)
      form.reset()
      // The sidebar and switcher list boards by name.
      if (body.name) void boards.fetchNav()
    }, 'Saved the name and description', { refresh: false })
  }

  return { ...form, nameError, descriptionError, valid, save }
}

export function useHandoverForm(page: BoardPage, status: BoardSettingsStatus) {
  const detail = computed(() => page.board.detail.value)
  const form = useSettingsDraft(() => {
    const board = detail.value?.board
    return board
      ? {
          enabled: board.handover_enabled,
          stageId: board.handover_stage_id,
          returnId: board.return_stage_id,
          target: board.handover_target_status as HandoverTarget,
        }
      : null
  })

  const stages = computed(() => detail.value?.stages ?? [])
  /** Handed-over cards sit in a Done stage; sent-back cards return to a To do one. */
  const doneStages = computed(() => stages.value.filter(s => s.category === 'done'))
  const todoStages = computed(() => stages.value.filter(s => s.category === 'todo'))

  const stageError = computed(() =>
    form.draft.value?.enabled && !form.draft.value.stageId
      ? 'Pick the Done stage cards are handed over from.'
      : '',
  )
  const valid = computed(() => form.dirty.value && !stageError.value)

  async function save(): Promise<boolean> {
    if (!valid.value) return false
    const changed = form.changes()
    const body: BoardUpdate = {}
    if (changed.enabled !== undefined) body.handover_enabled = changed.enabled
    if (changed.stageId !== undefined) body.handover_stage_id = changed.stageId
    if (changed.returnId !== undefined) body.return_stage_id = changed.returnId
    if (changed.target !== undefined) body.handover_target_status = changed.target
    return status.run(async key => {
      page.board.detail.value = await boardSettingsApi.update(key, body)
      form.reset()
    }, 'Saved the handover settings', { refresh: false })
  }

  return { ...form, doneStages, todoStages, stageError, valid, save }
}
