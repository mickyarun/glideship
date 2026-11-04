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

/** How the check-in page shows the state of its AI draft. */
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CheckInPage from '@/components/appraisals/CheckInPage.vue'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import { useCheckInsStore } from '@/stores/checkIns'
import type { CheckInRead } from '@/types/appraisal'

const FACT = {
  source: 'board_cards', id: 'f1', key: 'OPS-1', title: 'Close', url: '/b', verb: 'done',
  done_at: null, private: false,
}

function checkIn(overrides: Partial<CheckInRead> = {}): CheckInRead {
  return {
    id: 'c1', profile_id: 'p1', user_id: 'u1', person_name: 'Priya', manager_name: 'Ravi',
    period_start: '2026-10-01', period_end: '2026-10-31', working_days: 22, available_days: '22',
    status: 'open', closed: false, can_edit: true, drafting_mode: 'ai', draft_status: 'ready',
    ai_lines: [], ai_hidden: false, can_regenerate: false, heading_meanings: {}, facts: [FACT],
    fact_tags: {}, note: { lines: {}, blocking: '', next_month: '' }, links: [], goals: [],
    identity_warnings: [],
    ...overrides,
  }
}

function page(overrides: Partial<CheckInRead> = {}) {
  const { plugins } = boardTestPlugins()
  return mount(CheckInPage, { global: { plugins: plugins as never[] }, props: { checkIn: checkIn(overrides) } })
}

afterEach(() => vi.useRealTimers())

describe('CheckInPage', () => {
  it('says manual mode has no AI and offers no redraft', () => {
    const text = page({ drafting_mode: 'manual', draft_status: 'none' }).text()
    expect(text).toContain('Nothing on this page is written by AI.')
    expect(text).not.toContain('AI draft')
    expect(text).not.toContain('Redraft')
  })

  it('shows the work while a draft is being written', () => {
    const wrapper = page({ draft_status: 'pending' })
    expect(wrapper.text()).toContain('The AI draft is being written.')
    expect(wrapper.find('.work__key').text()).toBe('OPS-1')
    wrapper.unmount()
  })

  it('still shows the work when the draft failed, with a way to retry', () => {
    const wrapper = page({ draft_status: 'failed', can_regenerate: true })
    expect(wrapper.text()).toContain("The AI summary isn't available right now.")
    expect(wrapper.text()).toContain('Try again')
    expect(wrapper.find('.work__key').exists()).toBe(true)
  })

  it('marks AI lines as AI and links what they cite', () => {
    const wrapper = page({ ai_lines: [{ section: 'team', text: 'Closed the month', fact_ids: ['f1'] }] })
    expect(wrapper.find('.ai__badge').text()).toBe('AI draft')
    expect(wrapper.find('.ai__line').text()).toContain('Closed the month')
    expect(wrapper.find('a.ai__cite').attributes('href')).toBe('/b')
  })

  it('keeps unsaved typing when a tag or redraft replaces the check-in', async () => {
    const wrapper = page({ drafting_mode: 'manual', draft_status: 'none' })
    const box = wrapper.findAll('textarea')[0]
    await box.setValue('Still typing this')
    await wrapper.setProps({ checkIn: checkIn({ drafting_mode: 'manual', draft_status: 'none', fact_tags: {} }) })
    expect((wrapper.findAll('textarea')[0].element as HTMLTextAreaElement).value).toBe('Still typing this')
  })

  it('takes the saved note when it really changed', async () => {
    const wrapper = page({ drafting_mode: 'manual', draft_status: 'none' })
    await wrapper.findAll('textarea')[0].setValue('Old')
    const saved = { lines: {}, blocking: 'Saved', next_month: '' }
    await wrapper.setProps({ checkIn: checkIn({ drafting_mode: 'manual', draft_status: 'none', note: saved }) })
    expect((wrapper.findAll('textarea')[0].element as HTMLTextAreaElement).value).toBe('Saved')
  })

  it('polls while a draft is pending and stops when it lands or the page goes', async () => {
    vi.useFakeTimers()
    const wrapper = page({ draft_status: 'pending' })
    const refresh = vi.spyOn(useCheckInsStore(), 'refreshDraft').mockResolvedValue()
    vi.advanceTimersByTime(15_000)
    expect(refresh).toHaveBeenCalledTimes(1)
    await wrapper.setProps({ checkIn: checkIn({ draft_status: 'ready' }) })
    vi.advanceTimersByTime(60_000)
    expect(refresh).toHaveBeenCalledTimes(1)
    await wrapper.setProps({ checkIn: checkIn({ draft_status: 'pending' }) })
    wrapper.unmount()
    vi.advanceTimersByTime(60_000)
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('tells a reader why the draft is hidden', () => {
    expect(page({ ai_hidden: true, can_edit: false }).text()).toContain("records you can't open")
  })
})
