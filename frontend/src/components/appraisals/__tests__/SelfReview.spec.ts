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

/** Your review on one page: goals, the overall rating in words, the quarter beside it. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ReviewEvidence from '@/components/appraisals/ReviewEvidence.vue'
import SelfReviewForm from '@/components/appraisals/SelfReviewForm.vue'
import { evidenceOptions, reviewSubtitle, reviewWaiting, selfProgress } from '@/utils/appraisalReview'
import { appraisalPlugins } from './mountAppraisal'
import { review } from './reviewFixture'

const twoGoals = review({
  goals: [
    { ...review().goals[0], measure: 'Live for everyone by 15 Dec' },
    { ...review().goals[0], id: 'g2', title: 'Fewer reopened bugs', self_evidence: ['f1'] },
  ],
})

async function mountForm() {
  const { plugins } = await appraisalPlugins()
  return mount(SelfReviewForm, { global: { plugins: plugins as never[] }, props: { review: twoGoals, options: evidenceOptions(twoGoals), busy: null } })
}

describe('your review', () => {
  it('asks how each goal ended, low to high, then two open answers, and counts what is complete', async () => {
    const wrapper = await mountForm()
    const pills = wrapper.findAll('[role="radiogroup"]')[0].findAll('[role="radio"]').map(b => b.text())
    expect(pills).toEqual(['Not yet', 'Partly', 'Achieved'])
    expect(wrapper.text()).toContain('Live for everyone by 15 Dec')
    expect(wrapper.text()).toContain('Ravi reads this next, then HR · 0 of 4 complete')
    for (const radio of wrapper.findAll('[role="radiogroup"]')) await radio.findAll('[role="radio"]')[1].trigger('click')
    expect(wrapper.text()).toContain('1 of 4 complete')
    await wrapper.find('textarea').setValue('Shipped refunds early')
    expect(wrapper.text()).toContain('2 of 4 complete')
    const empty = { band: 3, reason: '', evidence: [], proud: '', differently: 'Start sooner', goals: [] }
    expect(selfProgress(empty)).toEqual({ done: 3, total: 4 })
  })

  it('asks for two examples for an Exceeded rating, and keeps each goal\'s earlier examples', async () => {
    const wrapper = await mountForm()
    for (const radio of wrapper.findAll('[role="radiogroup"]')) await radio.findAll('[role="radio"]')[2].trigger('click')
    await wrapper.find('input[type="radio"][value="1"]').setValue(true)
    const send = () => wrapper.findAll('button').find(b => b.text() === 'Send to Ravi')!
    expect(wrapper.text()).toContain('"Exceeded every time" needs 2 examples.')
    expect(send().attributes('disabled')).toBeDefined()
    for (const box of wrapper.findAll('.evidence input[type="checkbox"]')) await box.setValue(true)
    expect(wrapper.text()).toContain('You have 2.')
    expect(send().attributes('disabled')).toBeUndefined()
    await send().trigger('click')
    const [sent] = wrapper.emitted('submit')![0] as [{ band: number; evidence: string[]; goals: { evidence: string[] }[] }]
    expect(sent.band).toBe(1)
    expect(sent.evidence).toEqual(['f1', 'link:l1'])
    expect(sent.goals[1].evidence).toEqual(['f1'])
    expect(sent).toMatchObject({ proud: '', differently: '' })
    expect(wrapper.text()).not.toMatch(/\bband\b/i)
  })

  it("shows each goal's earlier examples, and sends only what is still shown", async () => {
    const wrapper = await mountForm()
    expect(wrapper.text()).toContain('Examples picked earlier:')
    await wrapper.find('button[aria-label="Remove OPS-1"]').trigger('click')
    expect(wrapper.text()).not.toContain('Examples picked earlier:')
    await wrapper.findAll('button').find(b => b.text() === 'Save')!.trigger('click')
    const [sent] = wrapper.emitted('save')![0] as [{ goals: { evidence: string[] }[] }]
    expect(sent.goals[1].evidence).toEqual([])
  })

  it('puts the quarter beside the form, each check-in with a link to open it', async () => {
    const { plugins } = await appraisalPlugins()
    const wrapper = mount(ReviewEvidence, { global: { plugins: plugins as never[] }, props: { review: twoGoals, isSelf: true } })
    expect(wrapper.text()).toContain('Your quarter at a glance')
    expect(wrapper.text()).toContain('October check-in')
    expect(wrapper.find('a[href="/appraisals/check-ins/c1"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('2 records')
    const theirs = mount(ReviewEvidence, { global: { plugins: plugins as never[] }, props: { review: twoGoals, isSelf: false } })
    expect(theirs.text()).toContain("Priya's quarter")
  })

  it('leads with what is due, and says who it waits on', () => {
    expect(reviewSubtitle(twoGoals)).toBe('Due Thu 7 Jan 2027')
    const withHr = review({ status: 'calibration', can: { ...twoGoals.can, edit_self: false } })
    expect(reviewWaiting(withHr, true)).toContain('fairness check')
  })
})
