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

/** The pill toggle's sizes, including the touch size whose track grows with its options. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createVuetify } from 'vuetify'
import AppPillToggle from '@/components/common/AppPillToggle.vue'

const OPTIONS = [
  { label: 'Backlog 3', value: 'a' },
  { label: 'In progress 12', value: 'b' },
  { label: 'Done 40', value: 'c' },
]

const mountToggle = (props: Record<string, unknown> = {}) =>
  mount(AppPillToggle, {
    global: { plugins: [createVuetify()] },
    props: { modelValue: 'a', options: OPTIONS, ...props },
  })

describe('AppPillToggle', () => {
  it('keeps md as the default size, so existing callers look the same', () => {
    expect(mountToggle().classes()).toContain('app-pill-toggle--md')
    expect(mountToggle({ size: 'sm' }).classes()).toContain('app-pill-toggle--sm')
  })

  it('has a touch size for rows of many options', () => {
    const wrapper = mountToggle({ size: 'touch', 'aria-label': 'Stages' })
    expect(wrapper.classes()).toContain('app-pill-toggle--touch')
    expect(wrapper.attributes('aria-label')).toBe('Stages')
    expect(wrapper.findAll('[role="radio"]').map(o => o.text())).toEqual(OPTIONS.map(o => o.label))
  })

  it('picks with a click or the arrow keys, as a radio group', async () => {
    const wrapper = mountToggle({ size: 'touch' })
    await wrapper.findAll('[role="radio"]')[1].trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['b'])
    await wrapper.trigger('keydown', { key: 'ArrowLeft' })
    expect(wrapper.emitted('update:modelValue')?.[1]).toEqual(['c'])
  })

  it('renders touch pills as separate radios: one picked, one tab stop', () => {
    const wrapper = mountToggle({ size: 'touch', modelValue: 'b' })
    const pills = wrapper.findAll('[role="radio"]')
    expect(pills.map(p => p.attributes('aria-checked'))).toEqual(['false', 'true', 'false'])
    expect(pills.map(p => p.classes().includes('app-pill-toggle__option--active'))).toEqual([false, true, false])
    expect(pills.map(p => p.attributes('tabindex'))).toEqual(['-1', '0', '-1'])
  })

  it('jumps to the first and last touch pill with Home and End', async () => {
    const wrapper = mountToggle({ size: 'touch', modelValue: 'b' })
    await wrapper.trigger('keydown', { key: 'End' })
    await wrapper.trigger('keydown', { key: 'Home' })
    expect(wrapper.emitted('update:modelValue')).toEqual([['c'], ['a']])
  })
})
