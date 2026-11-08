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

/** Goals and reviews on screen: actions, the evidence rules, agree or change, calibration. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CalibrationPanel from '@/components/appraisals/CalibrationPanel.vue'
import GrowthSection from '@/components/appraisals/GrowthSection.vue'
import GoalCard from '@/components/appraisals/GoalCard.vue'
import ManagerReviewForm from '@/components/appraisals/ManagerReviewForm.vue'
import SelfReviewForm from '@/components/appraisals/SelfReviewForm.vue'
import type { Goal } from '@/types/appraisalGoals'
import type { AppraisalRead } from '@/types/appraisalReview'
import { evidenceOptions, selfProblem } from '@/utils/appraisalReview'
import { goalSections, historyLine } from '@/utils/appraisalGoals'
import { appraisalPlugins } from './mountAppraisal'

const NONE = { accept: false, dismiss: false, ask_reword: false, edit: false, remove: false, suggest_change: false }

function goal(overrides: Partial<Goal> = {}): Goal {
  return {
    id: 'g1', position: null, title: 'Refunds UAT at 80%', measure: 'test report', origin: 'employee_own',
    status: 'proposed', suggestion_basis: null, proposed_by_name: 'Priya', added_mid_period: false,
    created_at: '2026-10-05T10:00:00Z', replaces: null, dismiss_reason: null, reword_note: null, why: null,
    history: [], actions: NONE, ...overrides,
  }
}

function review(overrides: Partial<AppraisalRead> = {}): AppraisalRead {
  return {
    id: 'a1', user_id: 'u1', person_name: 'Priya S', manager_name: 'Ravi', cycle_name: 'Q4 2026',
    period_start: '2026-10-01', period_end: '2026-12-31', self_due: '2027-01-07', manager_due: '2027-01-14',
    ack_due: '2027-01-28', status: 'self_review', drafting_mode: 'manual', summary_status: 'none', summary: [],
    summary_hidden: false, period_facts: [],
    timeline: [{
      check_in_id: 'c1', period_start: '2026-10-01', status: 'employee_added', note: { lines: {}, blocking: '', next_month: '' },
      facts: [{ source: 'board_cards', id: 'f1', key: 'OPS-1', title: 'Close', url: '/b', verb: 'done', done_at: null, private: false }],
      links: [{ id: 'l1', url: 'https://doc.test', title: 'Spec', heading: 'team', goal_id: null }],
    }],
    goals: [{ id: 'g1', position: 1, title: 'Ship refunds', measure: '', added_mid_period: false, accepted_at: null, self_result: null, self_reason: null, self_evidence: [], result: null, draft_result: null, manager_reason: null }],
    self_score: { band: null, reason: '', evidence: [], submitted_at: null },
    manager_score: null, manager_only: null, send_back_note: null, reply: null, shared_at: null, acknowledged_at: null,
    growth: { open: false, can_edit: false, strength: '', focus: '', next_period_start: '2027-01-01', limit: 3, goals: [] },
    can: { edit_self: true, edit_manager: false, send_back: false, share: false, acknowledge: false },
    ...overrides,
  }
}

describe('goals', () => {
  it('shows only the actions the caller has, and waits on the manager', async () => {
    const { plugins } = await appraisalPlugins()
    const wrapper = mount(GoalCard, {
      global: { plugins: plugins as never[] },
      props: { goal: goal({ actions: { ...NONE, edit: true, dismiss: true } }), managerName: 'Ravi', asEmployee: true },
    })
    expect(wrapper.text()).toContain('Waiting for Ravi to confirm.')
    expect(wrapper.findAll('button').map(b => b.text())).toEqual(['Edit', 'Withdraw'])
  })

  it('labels suggestions with their source and why', async () => {
    const { plugins } = await appraisalPlugins()
    const wrapper = mount(GoalCard, {
      global: { plugins: plugins as never[] },
      props: {
        goal: goal({ status: 'suggested', origin: 'ai_suggested', suggestion_basis: 'feedback', why: 'From the try-next line', actions: { ...NONE, accept: true, dismiss: true } }),
        managerName: 'Ravi',
        asEmployee: true,
      },
    })
    expect(wrapper.text()).toContain('From your feedback')
    expect(wrapper.text()).toContain('Why this: From the try-next line')
    expect(wrapper.findAll('button').map(b => b.text())).toEqual(['Use this goal', 'Dismiss'])
  })

  it('words history and groups goals', () => {
    const line = historyLine({
      kind: 'edited', by_name: 'Ravi', at: '2026-12-08T10:00:00Z', before: { title: 'Old', measure: '' },
      after: { title: 'New', measure: '' }, reason: 'Scope moved',
    })
    expect(line).toBe('Changed by Ravi on 8 Dec, from “Old”: Scope moved')
    const sections = goalSections([goal(), goal({ id: 'g2', status: 'accepted' }), goal({ id: 'g3', status: 'dismissed' })])
    expect([sections.accepted.length, sections.waiting.length, sections.dismissed.length]).toEqual([1, 1, 1])
  })
})

describe('self-review', () => {
  it('needs two pieces of evidence for band 1 or 2, and every goal scored', () => {
    const body = { band: 2, reason: '', evidence: ['f1'], goals: [{ goal_id: 'g1', result: 'achieved' as const, reason: '', evidence: [] }] }
    expect(selfProblem(body, ['g1'])).toContain('two pieces of evidence')
    expect(selfProblem({ ...body, evidence: ['f1', 'link:l1'] }, ['g1'])).toBe('')
    expect(selfProblem({ ...body, band: 3, goals: [] }, ['g1'])).toContain('Score each goal')
  })

  it('offers the period as evidence and blocks submitting until the rules are met', async () => {
    expect(evidenceOptions(review()).map(o => o.id)).toEqual(['f1', 'link:l1'])
    const { plugins } = await appraisalPlugins()
    const r = review()
    const wrapper = mount(SelfReviewForm, { global: { plugins: plugins as never[] }, props: { review: r, options: evidenceOptions(r), busy: null } })
    const submit = () => wrapper.findAll('button').find(b => b.text().startsWith('Submit'))
    expect(submit()?.attributes('disabled')).toBeDefined()
    await wrapper.findAll('[role="radio"]').find(b => b.text() === 'Achieved')?.trigger('click')
    await wrapper.findAll('[role="radio"]').find(b => b.text() === 'Meets always (3)')?.trigger('click')
    expect(submit()?.attributes('disabled')).toBeUndefined()
    await submit()?.trigger('click')
    const [sent] = wrapper.emitted('submit')![0] as [{ band: number; goals: { result: string }[] }]
    expect(sent.band).toBe(3)
    expect(sent.goals[0].result).toBe('achieved')
  })
})

describe('manager review', () => {
  it("can't agree without a self-score, and agree copies the employee's value", async () => {
    const { plugins } = await appraisalPlugins()
    const skipped = review({ status: 'manager_review', can: { ...review().can, edit_self: false, edit_manager: true } })
    const wrapper = mount(ManagerReviewForm, { global: { plugins: plugins as never[] }, props: { review: skipped, options: [], busy: null } })
    const agrees = wrapper.findAll('[role="radio"]').filter(b => b.text() === 'Agree')
    expect(agrees.every(b => b.attributes('disabled') !== undefined)).toBe(true)
    const scored = review({
      status: 'manager_review',
      self_score: { band: 3, reason: 'Steady', evidence: [], submitted_at: '2027-01-05T10:00:00Z' },
      goals: [{ ...review().goals[0], self_result: 'achieved' }],
      can: { ...review().can, edit_self: false, edit_manager: true },
    })
    const agreeing = mount(ManagerReviewForm, { global: { plugins: plugins as never[] }, props: { review: scored, options: [], busy: null } })
    await agreeing.findAll('button').find(b => b.text() === 'Submit to HR')?.trigger('click')
    const [body] = agreeing.emitted('submit')![0] as [{ agree: boolean; goals: { agree: boolean }[] }]
    expect(body.agree).toBe(true)
    expect(body.goals[0].agree).toBe(true)
  })
})

describe('calibration', () => {
  it('shows agreement and flags', async () => {
    const { plugins } = await appraisalPlugins()
    const wrapper = mount(CalibrationPanel, {
      global: { plugins: plugins as never[] },
      props: {
        calibration: {
          teams: [{ manager_name: 'Ravi', people: 3, bands: { '3': 3 }, agreement: 1, gaps: 0, flag: 'Agreed with every self-score.' }],
          people: [{ appraisal_id: 'a1', name: 'Priya', manager_name: 'Ravi', status: 'calibration', self_band: 1, final_band: 3, gap: true, feedback: 2, feedback_done: 1 }],
        },
      },
    })
    expect(wrapper.text()).toContain('100%')
    expect(wrapper.text()).toContain('Agreed with every self-score.')
    expect(wrapper.find('.calib__gap').exists()).toBe(true)
  })
})

describe('review fixes', () => {
  it('keeps a reopened "change" draft as a change, with its reason box', async () => {
    const { plugins } = await appraisalPlugins()
    const drafted = review({
      status: 'manager_review',
      self_score: { band: 3, reason: '', evidence: [], submitted_at: '2027-01-05T10:00:00Z' },
      goals: [{ ...review().goals[0], self_result: 'achieved', draft_result: 'partly', manager_reason: 'Half shipped' }],
      can: { ...review().can, edit_self: false, edit_manager: true },
    })
    const wrapper = mount(ManagerReviewForm, { global: { plugins: plugins as never[] }, props: { review: drafted, options: [], busy: null } })
    expect((wrapper.find('input[type="text"]').element as HTMLInputElement).value).toBe('Half shipped')
    await wrapper.findAll('button').find(b => b.text() === 'Submit to HR')?.trigger('click')
    const [body] = wrapper.emitted('submit')![0] as [{ goals: { agree: boolean; result: string }[] }]
    expect(body.goals[0]).toMatchObject({ agree: false, result: 'partly' })
  })

  it("won't confirm into a full period unless the goal replaces one", async () => {
    const { plugins } = await appraisalPlugins()
    const proposal = goal({ actions: { ...NONE, accept: true } })
    const full = mount(GoalCard, { global: { plugins: plugins as never[] }, props: { goal: proposal, managerName: 'Ravi', asEmployee: false, full: true } })
    expect(full.find('button').attributes('disabled')).toBeDefined()
    const change = mount(GoalCard, { global: { plugins: plugins as never[] }, props: { goal: { ...proposal, replaces: 'g0' }, managerName: 'Ravi', asEmployee: false, full: true } })
    expect(change.find('button').attributes('disabled')).toBeUndefined()
  })
})

describe('growth conversation', () => {
  it('shows no band, and offers confirm and take back by right', async () => {
    const { plugins } = await appraisalPlugins()
    const wrapper = mount(GrowthSection, {
      global: { plugins: plugins as never[] },
      props: {
        busy: null,
        growth: {
          open: true, can_edit: true, strength: 'Early regressions', focus: 'Plan UAT', next_period_start: '2027-01-01', limit: 3,
          goals: [
            { id: 'n1', title: 'UAT at 90%', measure: '', status: 'proposed', origin: 'employee_own', proposed_by_name: 'Priya', can_accept: true, can_remove: true },
          ],
        },
      },
    })
    expect(wrapper.text()).not.toMatch(/band|exceeds|meets/i)
    expect(wrapper.text()).toContain('Proposed by Priya')
    await wrapper.findAll('button').find(b => b.text() === 'Confirm')?.trigger('click')
    expect(wrapper.emitted('accept')![0]).toEqual(['n1'])
  })
})
