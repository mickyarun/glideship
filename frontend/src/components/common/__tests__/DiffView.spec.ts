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
 * The pure diff pair: DiffView shows what changed between two texts, and
 * VersionRail lists versions and reports the one picked.
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

import DiffView from '@/components/common/DiffView.vue'
import VersionRail from '@/components/common/VersionRail.vue'
import { diffStats, lineDiff } from '@/utils/lineDiff'

const global = { plugins: [createVuetify({ components, directives })] }
const lineTexts = (w: { findAll: (s: string) => { text: () => string }[] }) =>
  w.findAll('.diff-line').map(n => n.text().replace(/\s+/g, ' ').trim())

describe('DiffView', () => {
  it('marks added and removed lines between the two texts', () => {
    const wrapper = mount(DiffView, { props: { old: 'Title\nOld line\nSame', new: 'Title\nNew line\nSame' }, global })
    const lines = lineTexts(wrapper)
    expect(lines).toEqual(['Title', '−Old line', '+New line', 'Same'])
    expect(wrapper.findAll('.diff-line--added')).toHaveLength(1)
    expect(wrapper.findAll('.diff-line--removed')).toHaveLength(1)
  })

  it('says so when nothing changed', () => {
    const wrapper = mount(DiffView, { props: { old: 'Same', new: 'Same', emptyText: 'Nothing changed' }, global })
    expect(wrapper.findAll('.diff-line')).toHaveLength(0)
    expect(wrapper.text()).toContain('Nothing changed')
  })

  it('counts the changed lines', () => {
    expect(diffStats(lineDiff('a\nb', 'a\nc\nd'))).toEqual({ added: 2, removed: 1 })
    expect(diffStats(lineDiff('a', 'a'))).toBeNull()
  })
})

describe('VersionRail', () => {
  const items = [
    { id: 'v2', label: 'v2', at: '2026-10-02T00:00:00Z', badge: { text: 'Current', color: 'primary' } },
    { id: 'v1', label: 'v1', at: '2026-10-01T00:00:00Z', note: 'Asha' },
  ]

  it('lists the versions with the picked one pressed, and reports a pick', async () => {
    const wrapper = mount(VersionRail, { props: { items, selectedId: 'v1', loading: false }, global })
    const buttons = wrapper.findAll('.diff-rail__item')
    expect(buttons.map(b => b.attributes('aria-pressed'))).toEqual(['false', 'true'])
    expect(buttons[0].text()).toContain('Current')
    expect(buttons[1].text()).toContain('Asha')
    await buttons[0].trigger('click')
    expect(wrapper.emitted('select')).toEqual([['v2']])
  })

  it('shows the empty text when there are no versions', () => {
    const wrapper = mount(VersionRail, { props: { items: [], selectedId: null, loading: false, emptyText: 'Never saved' }, global })
    expect(wrapper.text()).toContain('Never saved')
  })
})
