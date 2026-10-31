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
 * A BUD handed over straight to design says ``design_pending``: its design
 * panel starts generating designs when it opens, once, and not for a BUD
 * that isn't pending.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createVuetify } from 'vuetify'

vi.mock('@/composables/useJobSocket', () => ({ useJobSocket: () => ({ startTracking: vi.fn() }) }))

import BUDDesignPanel from '@/components/buds/BUDDesignPanel.vue'
import { useBUDStore } from '@/stores/bud'
import { useDesignSystemStore } from '@/stores/designSystem'
import { useSettingsStore } from '@/stores/settings'
import type { BUDDocument, RepoInfo } from '@/types'

const BUD_ID = 'b2'

async function openPanel(pending: boolean) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const buds = useBUDStore()
  buds.currentBUD = { id: BUD_ID, status: 'design', design_pending: pending, figma_url: null, auto_generate_phases: { design: true } } as unknown as BUDDocument
  vi.spyOn(buds, 'fetchDesigns').mockResolvedValue([])
  vi.spyOn(buds, 'refreshBUDIfCurrent').mockResolvedValue(undefined as never)
  const generate = vi.spyOn(buds, 'generateDesigns').mockResolvedValue([])
  const settings = useSettingsStore()
  settings.repos = [{ id: 'r1', status: 'active' } as RepoInfo]
  vi.spyOn(settings, 'fetchRepos').mockResolvedValue()
  const systems = useDesignSystemStore()
  systems.items = [{ repo_id: 'r1' } as never]
  vi.spyOn(systems, 'fetchAll').mockResolvedValue()
  mount(BUDDesignPanel, { props: { budId: BUD_ID, editable: true }, global: { plugins: [createVuetify(), pinia] } })
  await flushPromises()
  return { buds, generate }
}

describe('BUDDesignPanel and a pending design', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('starts the designs of a BUD handed over to design, once', async () => {
    const { buds, generate } = await openPanel(true)
    expect(generate).toHaveBeenCalledWith(BUD_ID, ['r1'])
    // The BUD reloads (still pending until a design row lands): no second start.
    buds.currentBUD = { ...(buds.currentBUD as BUDDocument) }
    await flushPromises()
    expect(generate).toHaveBeenCalledTimes(1)
  })

  it('leaves a BUD that is not pending alone', async () => {
    const { generate } = await openPanel(false)
    expect(generate).not.toHaveBeenCalled()
  })
})
