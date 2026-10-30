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

/** Quick-add: Enter adds and stays open, typing carries on while it saves, Esc closes. */
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import BoardQuickAdd from '@/components/boards/board/BoardQuickAdd.vue'
import type { ActionResult } from '@/stores/boardCardActions'

const OK: ActionResult = { error: null, shown: true }

function setup(submitCard = vi.fn(async (): Promise<ActionResult> => OK)) {
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
  it('has a visible label and the key hint', async () => {
    const { wrapper } = setup()
    await openComposer(wrapper)
    expect(wrapper.text()).toContain('New card title')
    expect(wrapper.text()).toContain('Enter adds and keeps this open · Esc closes')
    wrapper.unmount()
  })

  it('adds on Enter, clears the box and stays open with focus in it', async () => {
    const { wrapper, submitCard } = setup()
    const box = await openComposer(wrapper)
    expect(box.attributes('maxlength')).toBe('120')
    await box.setValue('  Write the launch post  ')
    await box.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(submitCard).toHaveBeenCalledWith('Write the launch post')
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('')
    expect(document.activeElement).toBe(wrapper.find('textarea').element)
    wrapper.unmount()
  })

  it('keeps taking titles while one saves, and adds them in order', async () => {
    let finish!: (r: ActionResult) => void
    const submitCard = vi.fn()
      .mockReturnValueOnce(new Promise<ActionResult>(r => (finish = r)))
      .mockResolvedValueOnce(OK)
    const { wrapper } = setup(submitCard)
    const box = await openComposer(wrapper)
    await box.setValue('First')
    await box.trigger('keydown', { key: 'Enter' })
    expect(box.attributes('disabled')).toBeUndefined()
    await box.setValue('Second')
    await box.trigger('keydown', { key: 'Enter' })
    expect(submitCard).toHaveBeenCalledTimes(1)
    finish(OK)
    await flushPromises()
    expect(submitCard.mock.calls.map(([t]) => t)).toEqual(['First', 'Second'])
    wrapper.unmount()
  })

  it('says when a card went to the bottom of a long stage', async () => {
    const { wrapper } = setup(vi.fn(async () => ({ error: null, shown: false })))
    const box = await openComposer(wrapper)
    await box.setValue('Deep')
    await box.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(wrapper.find('[role="status"]').text()).toBe('Added "Deep" to the bottom of To do.')
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

  it('gives the text back and shows the error when the add fails', async () => {
    const { wrapper } = setup(vi.fn(async () => ({ error: 'Board is archived', shown: false })))
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
