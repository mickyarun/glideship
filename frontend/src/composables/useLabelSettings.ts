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

// A board's labels as its settings edit them: add, rename, recolour and
// delete. Names are unique per board; colours are the theme's label-* hues.

import { computed } from 'vue'
import type { BoardPage } from '@/composables/useBoardPage'
import type { BoardSettingsStatus } from '@/composables/useBoardSettingsStatus'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import type { LabelColor, LabelRead } from '@/types/boards'
import { uniqueNameBlock } from '@/utils/uniqueName'

export function useLabelSettings(page: BoardPage, status: BoardSettingsStatus) {
  const labels = computed(() =>
    [...(page.board.detail.value?.labels ?? [])].sort((a, b) => a.name.localeCompare(b.name)),
  )

  /** Why a label name can't be used, or null when it can. */
  function nameBlock(name: string, exceptId: string | null = null): string | null {
    return uniqueNameBlock(labels.value, name, exceptId, 'label')
  }

  function create(name: string, color: LabelColor): Promise<boolean> {
    const trimmed = name.trim()
    return status.run(key => boardSettingsApi.createLabel(key, { name: trimmed, color }), `Added the ${trimmed} label`)
  }

  function rename(label: LabelRead, name: string): Promise<boolean> {
    const next = name.trim()
    if (next === label.name) return Promise.resolve(true)
    return status.run(key => boardSettingsApi.updateLabel(key, label.id, { name: next }), `Renamed ${label.name} to ${next}`)
  }

  function recolor(label: LabelRead, color: LabelColor): Promise<boolean> {
    if (color === label.color) return Promise.resolve(true)
    return status.run(key => boardSettingsApi.updateLabel(key, label.id, { color }), `${label.name} is now ${color}`)
  }

  function remove(label: LabelRead): Promise<boolean> {
    return status.run(key => boardSettingsApi.deleteLabel(key, label.id), `Deleted the ${label.name} label`)
  }

  return { labels, nameBlock, create, rename, recolor, remove }
}

export type LabelSettings = ReturnType<typeof useLabelSettings>
