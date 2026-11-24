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

/** Starting a cycle: three short steps over the cycle's own settings. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CycleRhythm from '@/components/appraisals/CycleRhythm.vue'
import CycleSetupForm from '@/components/appraisals/CycleSetupForm.vue'
import type { CycleRead } from '@/types/appraisalSetup'
import { cycleForm, periodNoun } from '@/utils/appraisalCycleForm'
import { appraisalPlugins } from './mountAppraisal'

const draft: CycleRead = {
  id: 'c1', name: 'Q1 2027', status: 'draft', period_start: '2027-01-01', period_end: '2027-03-31',
  self_due: '2027-04-07', manager_due: '2027-04-14', ack_due: '2027-04-28', review_period: 'quarterly',
  checkin_cadence: 'monthly', feedback_cadence: 'monthly', feedback_due_days: 10, reminder_offsets: [-3, 0, 2],
  overdue_nudge: true, hr_overdue_list: true, hr_overdue_offset: 3, ai_drafting: true, suggest_goals_on_open: false,
  enrolment_cutoff: '2027-01-15', scope: { offices: [], departments: [], templates: [] }, template_overrides: {}, intro_note: '',
}

describe('new cycle', () => {
  it('shows who and when, then how it runs, with no goals-per-person field', async () => {
    const { plugins } = await appraisalPlugins()
    const wrapper = mount(CycleSetupForm, { global: { plugins: plugins as never[] }, props: { cycle: draft, saving: false, people: 41 } })
    expect(wrapper.findAll('.form-step__title').map(h => h.text())).toEqual(['Who and when', 'How the quarter runs'])
    expect(wrapper.text()).toContain('41 people')
    expect(wrapper.text()).not.toMatch(/goals per person/i)
    expect(wrapper.text()).toContain('Offer AI first drafts')
    await wrapper.find('input[maxlength="120"]').setValue('Q1 2027 pilot')
    expect(wrapper.emitted('dirty')!.at(-1)).toEqual([true])
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('save')![0][0]).toMatchObject({ name: 'Q1 2027 pilot', checkin_cadence: 'monthly', feedback_cadence: 'monthly' })
  })

  it('labels quarterly check-ins as once at quarter end, and greys out what cannot run', async () => {
    const { plugins } = await appraisalPlugins()
    const quarterly = mount(CycleRhythm, {
      global: { plugins: plugins as never[] },
      props: { review: 'quarterly', checkIns: 'monthly', notes: 'monthly' },
    })
    const checkIns = quarterly.findAll('[role="radiogroup"]')[0].findAll('[role="radio"]')
    expect(checkIns.map(b => b.text())).toEqual(['Every month', 'Once, at quarter end'])
    expect(checkIns[1].attributes('disabled')).toBeDefined()
    const notes = quarterly.findAll('[role="radiogroup"]')[1].findAll('[role="radio"]')
    expect(notes.map(b => [b.text(), b.attributes('disabled') !== undefined])).toEqual([
      ['After each check-in', false], ['Once, at quarter end', true], ['Only at review', false],
    ])
    const yearly = mount(CycleRhythm, { global: { plugins: plugins as never[] }, props: { review: 'yearly', checkIns: 'monthly', notes: 'monthly' } })
    await yearly.findAll('[role="radio"]').find(b => b.text() === 'Once, at quarter end')!.trigger('click')
    expect(yearly.emitted('update:checkIns')![0]).toEqual(['quarterly'])
  })

  it('copies the cycle for the form and names the period', () => {
    const form = cycleForm(draft)
    form.reminder_offsets.push(5)
    expect(draft.reminder_offsets).toEqual([-3, 0, 2])
    expect(periodNoun('half_yearly')).toBe('half-year')
  })
})
