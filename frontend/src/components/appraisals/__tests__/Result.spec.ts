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

/** The rating words and the shared result: scale, how it came about, reading it. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AcknowledgeBox from '@/components/appraisals/AcknowledgeBox.vue'
import BandScale from '@/components/appraisals/BandScale.vue'
import GrowthSection from '@/components/appraisals/GrowthSection.vue'
import ReviewResult from '@/components/appraisals/ReviewResult.vue'
import { BANDS, bandLabel, bandMeaning, evidenceNeeded, isHighBand, withBandWords } from '@/utils/appraisalBands'
import { overallLine } from '@/utils/appraisalReview'
import { periodWord } from '@/utils/appraisalSetup'
import { appraisalPlugins } from './mountAppraisal'
import { review } from './reviewFixture'

const shared = review({
  status: 'shared',
  shared_at: '2027-01-27T10:00:00Z',
  self_score: { band: 2, reason: 'Two goals early', evidence: [], submitted_at: '2027-01-05T10:00:00Z', proud: '', differently: 'Start write-ups sooner' },
  manager_score: { band: 2, reason: '', evidence: [], final_band: 2, submitted_at: '2027-01-12T10:00:00Z' },
  goals: [
    { ...review().goals[0], self_result: 'achieved', result: 'achieved' },
    { ...review().goals[0], id: 'g2', title: 'Help a new joiner', self_result: 'partly', result: 'achieved', manager_reason: 'They ship alone now' },
  ],
  can: { edit_self: false, edit_manager: false, send_back: false, share: false, acknowledge: true },
})

describe('rating words', () => {
  it('maps the stored band to words in one place, lowest first', () => {
    expect(BANDS.map(b => b.label)).toEqual([
      'Did not meet', 'Met sometimes', 'Met every time', 'Exceeded most times', 'Exceeded every time',
    ])
    expect(BANDS.map(b => b.value)).toEqual([5, 4, 3, 2, 1])
    expect(bandLabel(1)).toBe('Exceeded every time')
    expect(bandLabel(null)).toBe('')
    expect(bandMeaning(3)).toBe('Did what the role needs, reliably')
  })

  it('needs two examples for either Exceeded rating, and one for a manager moving to Did not meet', () => {
    expect([1, 2, 3].map(isHighBand)).toEqual([true, true, false])
    expect(evidenceNeeded(2, false)).toBe(2)
    expect(evidenceNeeded(5, false)).toBe(0)
    expect(evidenceNeeded(5, true)).toBe(1)
    expect(evidenceNeeded(3, true)).toBe(0)
  })

  it('fills the rating words into copy kept outside code', () => {
    expect(withBandWords('{high_bands} need {high_evidence}; {low_band} one.')).toBe(
      'Both "Exceeded" ratings need 2; "Did not meet" one.',
    )
  })

  it('shows five words with meanings, low to high, and no numbers', async () => {
    const { plugins } = await appraisalPlugins()
    const wrapper = mount(BandScale, { global: { plugins: plugins as never[] }, props: { modelValue: null, label: 'Overall rating' } })
    expect(wrapper.findAll('.band-scale__word').map(w => w.text())).toEqual(BANDS.map(b => b.label))
    expect(wrapper.text()).toContain('Missed most of what the role needs')
    expect(wrapper.text()).not.toMatch(/\d/)
    await wrapper.find('input[value="2"]').setValue(true)
    expect(wrapper.emitted('update:modelValue')![0]).toEqual([2])
  })
})

describe('shared result', () => {
  it('says how the rating came about', () => {
    expect(overallLine(shared, true)).toBe('You picked the same. Ravi agreed.')
    const changed = { ...shared, manager_score: { ...shared.manager_score!, final_band: 3, reason: 'Steady' } }
    expect(overallLine(changed, false)).toBe('Priya picked "Exceeded most times". Ravi changed it.')
    expect(overallLine({ ...shared, self_score: null }, true)).toContain('no self-review')
    expect(periodWord('quarterly')).toBe('quarter')
    expect(periodWord('yearly')).toBe('year')
  })

  it('shows the rating in words and each goal as agreed or changed, with the reason', async () => {
    const { plugins } = await appraisalPlugins()
    const wrapper = mount(ReviewResult, { global: { plugins: plugins as never[] }, props: { review: shared, isSelf: true } })
    expect(wrapper.find('.result__word').text()).toBe('Exceeded most times')
    const rows = wrapper.findAll('tbody tr').map(r => r.text())
    expect(rows[0]).toContain('Agreed')
    expect(rows[1]).toContain('Changed to Achieved')
    expect(rows[1]).toContain('They ship alone now')
    expect(wrapper.find('input[value="2"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('In your words')
    expect(wrapper.text()).toContain('Would do differently“Start write-ups sooner”')
  })

  it('says a goal was rated, not changed, when there was no self-review', async () => {
    const { plugins } = await appraisalPlugins()
    const unscored = { ...shared, goals: [{ ...shared.goals[0], self_result: null, result: 'partly' as const }] }
    const wrapper = mount(ReviewResult, { global: { plugins: plugins as never[] }, props: { review: unscored, isSelf: true } })
    expect(wrapper.find('tbody tr').text()).toContain('Rated Partly')
  })

  it("confirms reading, not agreeing, with an optional reply", async () => {
    const { plugins } = await appraisalPlugins()
    const wrapper = mount(AcknowledgeBox, { global: { plugins: plugins as never[] }, props: { review: shared, isSelf: true, busy: false } })
    expect(wrapper.text()).toContain("This confirms you've read it. It doesn't mean you agree.")
    await wrapper.find('textarea').setValue('  Fair  ')
    await wrapper.findAll('button').find(b => b.text() === "I've read this")?.trigger('click')
    expect(wrapper.emitted('acknowledge')![0]).toEqual(['Fair'])
    const done = mount(AcknowledgeBox, {
      global: { plugins: plugins as never[] },
      props: { review: { ...shared, can: { ...shared.can, acknowledge: false }, acknowledged_at: '2027-01-28T09:00:00Z', reply: 'Fair' }, isSelf: true, busy: false },
    })
    expect(done.text()).toBe('You read this on Thu 28 Jan 2027, replying: “Fair”')
  })

  it('names the plan for the period and who a proposal waits on', async () => {
    const { plugins } = await appraisalPlugins()
    const growth = {
      open: true, can_edit: true, is_self: true, strength: '', focus: '', next_period_start: '2027-01-01', limit: 3,
      goals: [{ id: 'n1', title: 'Lead the design', measure: '', status: 'proposed' as const, origin: 'employee_own', proposed_by_name: 'Priya', can_accept: false, can_remove: true }],
    }
    const wrapper = mount(GrowthSection, { global: { plugins: plugins as never[] }, props: { growth, busy: null, manager: 'Ravi' } })
    expect(wrapper.text()).toContain('Plan for next quarter')
    expect(wrapper.text()).toContain('Waiting for Ravi to confirm')
  })
})
