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

/** Quick-add: Enter adds and keeps the box open for the next card; Esc closes it. */
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import BoardQuickAdd from '@/components/boards/board/BoardQuickAdd.vue'

function setup(submitCard = vi.fn(async () => null as string | null)) {
  const { plugins } = boardTestPlugins()
  const wrapper = mount(BoardQuickAdd, {
    global: { plugins: plugins as never[] },
    props: { stageName: 'To do', maxLength: 120, submitCard },
    attachTo: document.body,
  })
  return { wrapper, submitCard }
}

async function openComposer(wrapper: ReturnType<typeof setup>['wrapper']) {
  await wrapper.find('button').trigger('click')
  await flushPromises()
  return wrapper.find('textarea')
}

describe('BoardQuickAdd', () => {
  it('adds on Enter, clears the box and stays open', async () => {
    const { wrapper, submitCard } = setup()
    const box = await openComposer(wrapper)
    expect(box.attributes('maxlength')).toBe('120')
    await box.setValue('  Write the launch post  ')
    await box.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(submitCard).toHaveBeenCalledWith('Write the launch post')
    expect(wrapper.find('textarea').exists()).toBe(true)
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('')
    wrapper.unmount()
  })

  it('ignores an empty title and Shift+Enter', async () => {
    const { wrapper, submitCard } = setup()
    const box = await openComposer(wrapper)
    await box.trigger('keydown', { key: 'Enter' })
    await box.setValue('Line one')
    await box.trigger('keydown', { key: 'Enter', shiftKey: true })
    expect(submitCard).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('keeps the text and shows the error when the add fails', async () => {
    const { wrapper } = setup(vi.fn(async () => 'Board is archived'))
    const box = await openComposer(wrapper)
    await box.setValue('Draft')
    await box.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(wrapper.text()).toContain('Board is archived')
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('Draft')
    wrapper.unmount()
  })

  it('closes on Escape and gives focus back to "Add a card"', async () => {
    const { wrapper } = setup()
    const box = await openComposer(wrapper)
    await box.trigger('keydown', { key: 'Escape' })
    await flushPromises()
    expect(wrapper.find('textarea').exists()).toBe(false)
    expect(document.activeElement?.textContent).toContain('Add a card')
    wrapper.unmount()
  })
})
