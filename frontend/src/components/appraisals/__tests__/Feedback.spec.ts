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

/** Manager feedback on screen: on the check-in, in the team list, and while writing it. */
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FeedbackRead, FeedbackRow } from '@/types/appraisalFeedback'

const apiGet = vi.fn()
const apiPut = vi.fn()
const apiPost = vi.fn()
vi.mock('@/services/api', () => ({ default: { get: apiGet, put: apiPut, post: apiPost } }))

const { default: CadenceFields } = await import('@/components/appraisals/CadenceFields.vue')
const { default: CheckInFeedback } = await import('@/components/appraisals/CheckInFeedback.vue')
const { default: TeamFeedbackList } = await import('@/components/appraisals/TeamFeedbackList.vue')
const { default: FeedbackView } = await import('@/views/appraisals/FeedbackView.vue')
const { appraisalPlugins } = await import('./mountAppraisal')

function item(overrides: Partial<FeedbackRead> = {}): FeedbackRead {
  return {
    id: 'f1', profile_id: 'p1', person_name: 'Priya', manager_name: 'Ravi',
    period_start: '2026-10-01', period_end: '2026-10-31', cadence: 'monthly', due_on: '2026-11-10',
    status: 'open', done_at: null, overdue: false, can_edit: true, keep: '', try_next: '', goals: [],
    check_ins: [{ id: 'c1', period_start: '2026-10-01', status: 'employee_added', closed: false }],
    ...overrides,
  }
}

beforeEach(() => {
  // The guide opens on a first visit; these specs are about the page under it.
  localStorage.setItem('appraisal-guide-seen', '1')
  apiGet.mockReset()
  apiPut.mockReset()
  apiPost.mockReset()
})

describe('CheckInFeedback', () => {
  it('shows what the manager saved, even before it is done', async () => {
    const { plugins } = await appraisalPlugins()
    const wrapper = mount(CheckInFeedback, {
      global: { plugins: plugins as never[] },
      props: {
        feedback: {
          manager_name: 'Ravi', period_start: '2027-01-01', period_end: '2027-03-31', cadence: 'quarterly',
          done: false, keep: 'Clear PRs', try_next: '', goals: [{ id: 'g', title: 'Clicks', status: 'at_risk', note: '' }],
        },
      },
    })
    expect(wrapper.text()).toContain("Ravi's feedback · Q1 2027")
    expect(wrapper.text()).toContain('still being written')
    expect(wrapper.text()).toContain('Keep: Clear PRs')
    expect(wrapper.text()).not.toContain('Try:')
    expect(wrapper.text()).toContain('Clicks · At risk')
  })
})

describe('TeamFeedbackList', () => {
  it('lists each period with who is done and who is overdue', async () => {
    const { plugins } = await appraisalPlugins()
    const base: Omit<FeedbackRow, 'id' | 'person_name' | 'status' | 'overdue'> = {
      profile_id: 'p', period_start: '2026-10-01', period_end: '2026-10-31', cadence: 'monthly',
      due_on: '2026-11-10', check_ins: 1, check_ins_added: 0,
    }
    const wrapper = mount(TeamFeedbackList, {
      global: { plugins: plugins as never[] },
      props: {
        rows: [
          { ...base, id: 'a', person_name: 'Sam', status: 'done', overdue: false },
          { ...base, id: 'b', person_name: 'Meena', status: 'open', overdue: true },
        ],
      },
    })
    expect(wrapper.find('.team-feedback__title').text()).toBe('October feedback · due Tue 10 Nov 2026 · 1 of 2 done')
    expect(wrapper.find('.team-feedback__late').text()).toBe('Overdue')
    const links = wrapper.findAll('a')
    expect(links.map(a => a.text())).toEqual(['Write feedback', 'Open'])
    expect(links[0].attributes('href')).toBe('/appraisals/feedback/b')
  })
})

describe('FeedbackView', () => {
  async function view(data: FeedbackRead) {
    apiGet.mockResolvedValue({ data })
    const { plugins } = await appraisalPlugins('/appraisals/feedback/f1')
    const wrapper = mount(FeedbackView, { global: { plugins: plugins as never[] } })
    await flushPromises()
    return wrapper
  }

  it('saves both lines, and only marks done once both are written', async () => {
    const wrapper = await view(item())
    expect(apiGet).toHaveBeenCalledWith('/v1/manager-feedback/f1')
    const done = () => wrapper.findAll('button').find(b => b.text() === 'Mark done')
    expect(done()?.attributes('disabled')).toBeDefined()
    const [keep, tryNext] = wrapper.findAll('textarea:not(.v-textarea__sizer)')
    await keep.setValue('Clear PRs')
    await tryNext.setValue('Pair on UAT')
    apiPut.mockResolvedValue({ data: item({ keep: 'Clear PRs', try_next: 'Pair on UAT' }) })
    apiPost.mockResolvedValue({ data: item({ keep: 'Clear PRs', try_next: 'Pair on UAT', status: 'done' }) })
    await done()?.trigger('click')
    await flushPromises()
    expect(apiPut).toHaveBeenCalledWith('/v1/manager-feedback/f1', { keep: 'Clear PRs', try_next: 'Pair on UAT', goals: [] })
    expect(apiPost).toHaveBeenCalledWith('/v1/manager-feedback/f1/done')
    expect(wrapper.text()).toContain('Marked done.')
  })

  it('keeps the typing and never marks done when the save fails', async () => {
    const wrapper = await view(item())
    const [keep, tryNext] = wrapper.findAll('textarea:not(.v-textarea__sizer)')
    await keep.setValue('Clear PRs')
    await tryNext.setValue('Pair on UAT')
    apiPut.mockRejectedValue(new Error('offline'))
    await wrapper.findAll('button').find(b => b.text() === 'Mark done')?.trigger('click')
    await flushPromises()
    expect(apiPost).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Network error. Please check your connection.')
    expect((keep.element as HTMLTextAreaElement).value).toBe('Clear PRs')
  })

  it('sends goal statuses, and asks for a status before keeping a note', async () => {
    const goals = [{ id: 'g1', title: 'Clicks +25%', status: null, note: '' }]
    const wrapper = await view(item({ cadence: 'quarterly', goals }))
    const note = wrapper.find('.fb-goals__goal input')
    await note.setValue('Behind in Sept')
    expect(wrapper.text()).toContain('Pick a status to keep this note.')
    await wrapper.findAll('[role="radio"]').find(r => r.text() === 'At risk')?.trigger('click')
    expect(wrapper.text()).not.toContain('Pick a status to keep this note.')
    apiPut.mockResolvedValue({ data: item({ cadence: 'quarterly', goals }) })
    await wrapper.findAll('button').find(b => b.text() === 'Save')?.trigger('click')
    await flushPromises()
    expect(apiPut.mock.calls[0][1].goals).toEqual([{ goal_id: 'g1', status: 'at_risk', note: 'Behind in Sept' }])
  })

  it('shows goal statuses without letting a reader change them', async () => {
    const goals = [{ id: 'g1', title: 'Clicks +25%', status: 'on_track' as const, note: '' }]
    const wrapper = await view(item({ cadence: 'quarterly', goals, can_edit: false }))
    const radios = wrapper.findAll('[role="radio"]')
    expect(radios.every(r => r.attributes('disabled') !== undefined)).toBe(true)
    expect(radios.find(r => r.text() === 'On track')?.attributes('aria-checked')).toBe('true')
  })

  it('is read-only for anyone but the manager', async () => {
    const wrapper = await view(item({ can_edit: false, keep: 'Clear PRs', try_next: 'Pair' }))
    expect(wrapper.findAll('button').some(b => b.text() === 'Save')).toBe(false)
    expect(wrapper.find('textarea:not(.v-textarea__sizer)').attributes('readonly')).toBeDefined()
  })
})

describe('CadenceFields', () => {
  it('explains a combination that cannot run', async () => {
    const { plugins } = await appraisalPlugins()
    const wrapper = mount(CadenceFields, {
      global: { plugins: plugins as never[] },
      props: { review: 'quarterly', checkIns: 'monthly', feedback: 'quarterly' },
    })
    expect(wrapper.find('[role="alert"]').text()).toContain('With quarterly reviews')
  })
})
