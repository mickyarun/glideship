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

/** The WIP limit: a count pill, and a warning row only once the count is over it. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { makeStage } from '@/components/boards/__tests__/fixtures'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import StageColumnHeader from '@/components/boards/board/StageColumnHeader.vue'

function header(count: number, wip_limit: number | null, extra: { archived?: boolean; more?: boolean } = {}) {
  const { plugins } = boardTestPlugins()
  return mount(StageColumnHeader, {
    global: { plugins: plugins as never[] },
    props: { id: 'h', count, stage: makeStage('s1', { name: 'Writing', category: 'in_progress', wip_limit }), ...extra },
  })
}

describe('StageColumnHeader', () => {
  it('warns once the count passes the limit', () => {
    const over = header(4, 3)
    expect(over.text()).toContain('4 / 3')
    expect(over.text()).toContain('Over the WIP limit of 3')
    expect(over.find('.stage-head__count--over').exists()).toBe(true)
  })

  it('is calm at the limit', () => {
    const at = header(3, 3)
    expect(at.text()).not.toContain('Over the WIP limit')
    expect(at.find('.stage-head__count--over').exists()).toBe(false)
  })

  it('treats a limit of 0 or none as no limit', () => {
    for (const limit of [0, null]) {
      const w = header(12, limit)
      expect(w.find('.stage-head__count [aria-hidden="true"]').text()).toBe('12')
      expect(w.text()).not.toContain('Over')
    }
  })

  it('counts archived cards loaded in the archived view, with no limit, "+" while more wait', () => {
    const w = header(5, 3, { archived: true, more: true })
    expect(w.find('.stage-head__count [aria-hidden="true"]').text()).toBe('5+')
    expect(w.find('.stage-head__count .d-sr-only').text()).toBe('5+ archived cards')
    expect(w.text()).not.toContain('Over the WIP limit')
    expect(header(1, null, { archived: true }).find('.stage-head__count .d-sr-only').text()).toBe('1 archived card')
  })

  it('names the category for screen readers', () => {
    expect(header(1, null).find('h2').attributes('aria-label')).toBe('Writing, In progress')
    expect(header(1, null).find('h2').text()).toBe('Writing')
  })
})
