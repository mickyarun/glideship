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
 * Where a column watches for its next page: inside its own scroll box on
 * wider screens, and against the window on phones, where the page scrolls.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import { makeStage } from '@/components/boards/__tests__/fixtures'
import BoardStageColumn from '@/components/boards/board/BoardStageColumn.vue'
import { emptyColumn } from '@/utils/boardColumns'

const roots: (Element | Document | null | undefined)[] = []
vi.stubGlobal('IntersectionObserver', class {
  constructor(_cb: IntersectionObserverCallback, options?: IntersectionObserverInit) {
    roots.push(options?.root)
  }
  observe(): void {}
  disconnect(): void {}
})

function mountColumn(phone: boolean) {
  const { pinia, router } = boardTestPlugins()
  // jsdom's window is 1024px wide: a high sm threshold makes it a phone.
  const vuetify = createVuetify({ components, directives, display: { thresholds: phone ? { sm: 4000 } : {} } })
  return mount(BoardStageColumn, {
    global: { plugins: [vuetify, pinia, router] },
    props: {
      stage: makeStage('s1'), column: emptyColumn(), count: 0, boardId: 'b1', boardKey: 'OPS',
      stages: [makeStage('s1')], labelsById: new Map(), now: new Date(),
      canDrag: false, canMove: false, canCreate: false, canArchive: false, titleMax: null,
      submitCard: async () => ({ error: null, shown: true }),
    },
  })
}

describe('BoardStageColumn', () => {
  afterEach(() => {
    roots.length = 0
  })

  it('watches its own scroll box for the next page', async () => {
    const wrapper = mountColumn(false)
    await flushPromises()
    expect(roots.at(-1)).toBe(wrapper.find('.stage-col__scroll').element)
  })

  it('watches the window on phones, where the page scrolls', async () => {
    mountColumn(true)
    await flushPromises()
    expect(roots.at(-1)).toBeNull()
  })
})
