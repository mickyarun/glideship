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

/** Save as you type: never on load, nothing typed mid-save is lost, saves don't overlap. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { useAutosave } from '@/composables/useAutosave'

function setup(persistDelay = 0) {
  const text = ref('')
  const saves: string[] = []
  let inFlight = 0
  let most = 0
  let api!: ReturnType<typeof useAutosave>
  const persist = async (): Promise<string | null> => {
    saves.push(text.value)
    most = Math.max(most, ++inFlight)
    await new Promise(r => setTimeout(r, persistDelay))
    inFlight--
    return null
  }
  const wrapper = mount(defineComponent({
    setup() {
      api = useAutosave(() => text.value, persist, () => true)
      return () => h('div')
    },
  }))
  return { text, saves, api, wrapper, overlap: () => most }
}

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

describe('useAutosave', () => {
  it('does not save a record just loaded', async () => {
    const { text, saves, api } = setup()
    text.value = 'from the server'
    api.reset()
    await nextTick()
    await vi.runAllTimersAsync()
    expect(saves).toEqual([])
    expect(api.state.value).toBe('saved')
  })

  it('keeps what was typed while a save was on its way, and never overlaps saves', async () => {
    const { text, saves, api, overlap } = setup(500)
    text.value = 'first'
    await nextTick()
    await vi.advanceTimersByTimeAsync(900)
    expect(saves).toEqual(['first'])
    text.value = 'first and more'
    await nextTick()
    const sent = api.flush()
    await vi.runAllTimersAsync()
    expect(await sent).toBe(true)
    expect(saves.at(-1)).toBe('first and more')
    expect(api.state.value).toBe('saved')
    expect(overlap()).toBe(1)
  })

  it('saves at once on flush, and what is left when the page closes', async () => {
    const { text, saves, api, wrapper } = setup()
    text.value = 'send me'
    await nextTick()
    const sent = api.flush()
    await vi.runAllTimersAsync()
    expect(await sent).toBe(true)
    expect(saves).toEqual(['send me'])
    text.value = 'leaving'
    await nextTick()
    wrapper.unmount()
    await vi.runAllTimersAsync()
    expect(saves).toEqual(['send me', 'leaving'])
  })
})

describe('leaving with unsaved text', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('asks the browser to confirm, and stops asking once saved', async () => {
    const { text, api } = setup()
    const ask = () => {
      const event = new Event('beforeunload', { cancelable: true })
      window.dispatchEvent(event)
      return event.defaultPrevented
    }
    expect(ask()).toBe(false)
    text.value = 'not saved yet'
    await nextTick()
    expect(ask()).toBe(true)
    const sent = api.flush()
    await vi.runAllTimersAsync()
    await sent
    expect(ask()).toBe(false)
  })
})
