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
 * The shared pieces' own behaviour: the confirm dialog gives focus back
 * when it closes, and pill toggles move with the arrow keys like radios.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@/components/boards/__tests__/mountHelpers'

import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'

const global = { plugins: [createVuetify({ components, directives })] }
const wait = () => new Promise(resolve => setTimeout(resolve, 350))

function confirmHarness(withFallback: boolean) {
  const open = ref(false)
  const shown = ref(true)
  const fallback = ref<HTMLElement | null>(null)
  const Host = defineComponent(() => () => [
    shown.value ? h('button', { id: 'opener', onClick: () => (open.value = true) }, 'Delete') : null,
    h('input', { id: 'add', ref: fallback }),
    h(AppConfirmDialog, {
      modelValue: open.value, title: 'Delete it?', action: 'Delete', color: 'error',
      returnFocus: withFallback ? fallback.value : null,
      'onUpdate:modelValue': (v: boolean) => (open.value = v),
    }),
  ])
  return { open, shown, wrapper: mount(Host, { global, attachTo: document.body }) }
}

describe('AppConfirmDialog focus', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('gives focus back to what opened it', async () => {
    const { open, wrapper } = confirmHarness(false)
    const opener = wrapper.find('#opener').element as HTMLElement
    opener.focus()
    open.value = true
    await flushPromises()
    await wait()
    ;(wrapper.find('#add').element as HTMLElement).focus()
    open.value = false
    await flushPromises()
    await wait()
    expect(document.activeElement).toBe(opener)
  })

  it('falls back to returnFocus when the opener is gone', async () => {
    const { open, shown, wrapper } = confirmHarness(true)
    ;(wrapper.find('#opener').element as HTMLElement).focus()
    open.value = true
    await flushPromises()
    await wait()
    shown.value = false
    open.value = false
    await flushPromises()
    await wait()
    expect(document.activeElement?.id).toBe('add')
  })
})

describe('AppPillToggle keys', () => {
  it('moves between options with the arrow keys, Home and End, with one tab stop', async () => {
    const value = ref('a')
    const options = [{ label: 'A', value: 'a' }, { label: 'B', value: 'b' }, { label: 'C', value: 'c' }]
    const wrapper = mount(() => h(AppPillToggle, {
      modelValue: value.value, options, 'onUpdate:modelValue': (v: string | number) => (value.value = String(v)),
    }), { global, attachTo: document.body })
    const tabStops = () => wrapper.findAll('[role="radio"]').map(r => r.attributes('tabindex'))
    expect(tabStops()).toEqual(['0', '-1', '-1'])
    await wrapper.find('[role="radiogroup"]').trigger('keydown', { key: 'ArrowRight' })
    expect(value.value).toBe('b')
    await wrapper.find('[role="radiogroup"]').trigger('keydown', { key: 'End' })
    expect(value.value).toBe('c')
    await wrapper.find('[role="radiogroup"]').trigger('keydown', { key: 'ArrowRight' })
    expect(value.value).toBe('a')
    await wrapper.find('[role="radiogroup"]').trigger('keydown', { key: 'ArrowLeft' })
    await flushPromises()
    expect(value.value).toBe('c')
    expect(tabStops()).toEqual(['-1', '-1', '0'])
    expect(document.activeElement?.textContent?.trim()).toBe('C')
    wrapper.unmount()
  })
})
