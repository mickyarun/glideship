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

// A board's stages as its settings edit them: add, rename, re-categorise,
// set the WIP limit and what a card needs to enter, make one the default
// (both refused inline, on the row, when the server says no), reorder (dragged, or one step
// with the arrow buttons) and delete, moving its cards elsewhere. The list
// follows the open board, so a change made elsewhere shows up here; a
// reorder shows at once and goes back if the server refuses it.

import { computed, ref, watch, type Ref } from 'vue'
import type { BoardPage } from '@/composables/useBoardPage'
import type { BoardSettingsStatus } from '@/composables/useBoardSettingsStatus'
import { CATEGORY_LABELS } from '@/constants/boards'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import type { BoardLimits, StageCategory, StageRead, StageRequiredField } from '@/types/boards'
import { addBlock, moveItem, movedId, requiredBlock } from '@/utils/boardStageRules'
import { needsList } from '@/utils/stageRules'

export interface NewStage {
  name: string
  category: StageCategory
  wip: number | null
}

export function useStageSettings(page: BoardPage, status: BoardSettingsStatus, limits: Ref<BoardLimits | null>) {
  const fromBoard = computed(() =>
    [...(page.board.detail.value?.stages ?? [])].sort((a, b) => a.position - b.position),
  )
  const list = ref<StageRead[]>([])
  // One reorder at a time; while it's in flight the shown order is the one sent.
  const reordering = ref(false)
  watch(fromBoard, next => {
    if (!reordering.value) list.value = next
  }, { immediate: true })

  const addError = computed(() => {
    const max = limits.value?.max_stages
    return max ? addBlock(list.value.length, max) : null
  })

  /** The server's refusal of a row's last change, by stage id, for changes the row explains itself. */
  const refusals = ref<Record<string, string>>({})
  // Any change going through settles what was refused before.
  watch(status.successes, () => (refusals.value = {}))

  function patch(stage: StageRead, body: Parameters<typeof boardSettingsApi.updateStage>[2], done: string) {
    return status.run(key => boardSettingsApi.updateStage(key, stage.id, body), done)
  }

  /** A change refused on its row rather than at the top of the page. */
  async function patchInline(stage: StageRead, body: Parameters<typeof patch>[1], done: string): Promise<boolean> {
    refusals.value = { ...refusals.value, [stage.id]: '' }
    const ok = await status.run(key => boardSettingsApi.updateStage(key, stage.id, body), done, { inline: true })
    if (!ok) refusals.value = { ...refusals.value, [stage.id]: status.inlineError.value }
    return ok
  }

  function add(stage: NewStage): Promise<boolean> {
    const name = stage.name.trim()
    return status.run(
      key => boardSettingsApi.createStage(key, { name, category: stage.category, wip_limit: stage.wip }),
      `Added the ${name} stage`,
    )
  }

  function rename(stage: StageRead, name: string): Promise<boolean> {
    const next = name.trim()
    if (next === stage.name) return Promise.resolve(true)
    return patch(stage, { name: next }, `Renamed ${stage.name} to ${next}`)
  }

  function setCategory(stage: StageRead, category: StageCategory): Promise<boolean> {
    if (category === stage.category) return Promise.resolve(true)
    return patch(stage, { category }, `${stage.name} is now a ${CATEGORY_LABELS[category]} stage`)
  }

  function setWip(stage: StageRead, wip: number | null): Promise<boolean> {
    if (wip === stage.wip_limit) return Promise.resolve(true)
    const done = wip === null ? `Removed the WIP limit on ${stage.name}` : `Set the WIP limit on ${stage.name} to ${wip}`
    return patch(stage, { wip_limit: wip }, done)
  }

  function makeDefault(stage: StageRead): Promise<boolean> {
    if (stage.is_default) return Promise.resolve(true)
    const block = requiredBlock({ ...stage, is_default: true }, stage.required_fields)
    if (block) {
      refusals.value = { ...refusals.value, [stage.id]: block }
      return Promise.resolve(false)
    }
    return patchInline(stage, { is_default: true }, `New cards now land in ${stage.name}`)
  }

  function setRequired(stage: StageRead, fields: StageRequiredField[]): Promise<boolean> {
    if (fields.join() === stage.required_fields.join()) return Promise.resolve(true)
    const done = fields.length
      ? `${stage.name} now needs ${needsList(fields)}`
      : `${stage.name} no longer needs anything to enter`
    return patchInline(stage, { required_fields: fields }, done)
  }

  /**
   * Save a new left-to-right order, showing it straight away. ``moved`` names
   * the stage for the announcement; a drag works it out from the two orders.
   */
  async function reorder(next: StageRead[], moved?: StageRead): Promise<boolean> {
    const before = list.value.map(s => s.id)
    const ids = next.map(s => s.id)
    if (!movedId(before, ids)) return true
    moved ??= next.find(s => s.id === movedId(before, ids))
    if (!moved || reordering.value) return true
    reordering.value = true
    list.value = next
    const done = `Moved ${moved.name} to position ${ids.indexOf(moved.id) + 1} of ${ids.length}`
    const ok = await status.run(key => boardSettingsApi.reorderStages(key, ids), done)
    reordering.value = false
    if (!ok) list.value = fromBoard.value
    return ok
  }

  /** Move a stage one place left (-1) or right (+1). */
  function step(stage: StageRead, delta: -1 | 1): Promise<boolean> {
    const from = list.value.findIndex(s => s.id === stage.id)
    return reorder(moveItem(list.value, from, from + delta), stage)
  }

  function remove(stage: StageRead, moveTo: StageRead | null): Promise<boolean> {
    const done = moveTo && stage.open_cards
      ? `Deleted ${stage.name} and moved its cards to ${moveTo.name}`
      : `Deleted the ${stage.name} stage`
    // The delete dialog shows its own refusal.
    return status.run(key => boardSettingsApi.deleteStage(key, stage.id, moveTo?.id ?? null), done, { inline: true })
  }

  return {
    list, reordering, addError, refusals,
    add, rename, setCategory, setWip, makeDefault, setRequired, reorder, step, remove,
  }
}

export type StageSettings = ReturnType<typeof useStageSettings>
