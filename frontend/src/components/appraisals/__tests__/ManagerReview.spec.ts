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

/** The manager's review: their answer beside agree-or-change, examples for big changes, HR-only answers. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ManagerReviewForm from '@/components/appraisals/ManagerReviewForm.vue'
import { evidenceOptions, managerDraft, managerProblem } from '@/utils/appraisalReview'
import { appraisalPlugins } from './mountAppraisal'
import { review } from './reviewFixture'

const scored = review({
  status: 'manager_review',
  self_score: { band: 3, reason: 'Steady quarter', evidence: [], submitted_at: '2027-01-05T10:00:00Z', proud: 'Shipped refunds early', differently: '' },
  goals: [{ ...review().goals[0], self_result: 'achieved', self_reason: 'Live three days early' }],
  can: { edit_self: false, edit_manager: true, send_back: false, share: false, acknowledge: false },
})

async function mountForm() {
  const { plugins } = await appraisalPlugins()
  return mount(ManagerReviewForm, { global: { plugins: plugins as never[] }, props: { review: scored, options: evidenceOptions(scored), busy: null } })
}

const send = (wrapper: Awaited<ReturnType<typeof mountForm>>) => wrapper.findAll('button').find(b => b.text() === 'Send to HR')!

describe('manager review', () => {
  it("shows the person's answer beside agree or change", async () => {
    const wrapper = await mountForm()
    expect(wrapper.text()).toContain('Achieved')
    expect(wrapper.text()).toContain('“Live three days early”')
    expect(wrapper.text()).toContain('Met every time')
    expect(wrapper.text()).toContain('“Steady quarter”')
    expect(wrapper.text()).toContain('Priya sees your answers after HR shares them.')
    expect(wrapper.text()).toContain('Most proud of“Shipped refunds early”')
    expect(wrapper.text()).not.toContain('Would do differently')
    expect(send(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('needs two examples to change the overall to an Exceeded rating', async () => {
    const wrapper = await mountForm()
    const overall = wrapper.findAll('[role="radiogroup"]').find(g => g.attributes('aria-label') === 'Agree or change the overall rating')!
    await overall.findAll('[role="radio"]')[1].trigger('click')
    await wrapper.find('input[type="radio"][value="2"]').setValue(true)
    await wrapper.find('textarea').setValue('Two goals early')
    expect(wrapper.text()).toContain('"Exceeded most times" needs 2 examples. You have 0.')
    expect(send(wrapper).attributes('disabled')).toBeDefined()
    for (const box of wrapper.findAll('.evidence input[type="checkbox"]')) await box.setValue(true)
    expect(send(wrapper).attributes('disabled')).toBeUndefined()
    await send(wrapper).trigger('click')
    const [body] = wrapper.emitted('submit')![0] as [{ agree: boolean; band: number; evidence: string[] }]
    expect(body).toMatchObject({ agree: false, band: 2, evidence: ['f1', 'link:l1'] })
  })

  it('drops picked examples when switching back to agree', async () => {
    const wrapper = await mountForm()
    const overall = () => wrapper.findAll('[role="radiogroup"]').find(g => g.attributes('aria-label') === 'Agree or change the overall rating')!
    await overall().findAll('[role="radio"]')[1].trigger('click')
    await wrapper.findAll('.evidence input[type="checkbox"]')[0].setValue(true)
    await overall().findAll('[role="radio"]')[0].trigger('click')
    await send(wrapper).trigger('click')
    const [body] = wrapper.emitted('submit')![0] as [{ agree: boolean; evidence: string[] }]
    expect(body).toMatchObject({ agree: true, evidence: [] })
  })

  it('asks HR-only questions with yes or no, and offers no send back', async () => {
    const wrapper = await mountForm()
    expect(wrapper.text()).toContain('Priya never sees this part.')
    const ready = wrapper.findAll('[role="radiogroup"]').find(g => g.attributes('aria-label') === 'Ready for the next level')!
    expect(ready.findAll('[role="radio"]').map(r => r.text())).toEqual(['Yes', 'No'])
    expect(wrapper.text()).not.toContain('Not sure')
    expect(wrapper.findAll('button').some(b => b.text().startsWith('Send back'))).toBe(false)
  })

  it('mirrors the server rules for changes', () => {
    const draft = managerDraft(scored)
    expect(draft.agree).toBe(true)
    expect(managerProblem(draft)).toBe('')
    expect(managerProblem({ ...draft, goals: [{ ...draft.goals[0], agree: false, result: 'partly', reason: '' }] })).toContain('Say why')
    const low = { ...draft, agree: false, band: 5, reason: 'Missed the launch' }
    expect(managerProblem(low)).toBe('"Did not meet" needs an example. Pick one under Examples.')
    expect(managerProblem({ ...low, evidence: ['f1'] })).toBe('')
    expect(managerProblem({ ...draft, agree: false, band: 4, reason: '' })).toContain('Say why')
  })
})
