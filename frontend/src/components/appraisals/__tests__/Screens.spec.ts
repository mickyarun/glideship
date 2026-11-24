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

/** The new screens' parts: the check-in's work list, the team queue, proposals, the cycle page. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CheckInWorkStep from '@/components/appraisals/CheckInWorkStep.vue'
import CycleRunning from '@/components/appraisals/CycleRunning.vue'
import ProposalCard from '@/components/appraisals/ProposalCard.vue'
import TeamQueue from '@/components/appraisals/TeamQueue.vue'
import type { FactView } from '@/types/appraisal'
import type { Goal } from '@/types/appraisalGoals'
import type { CycleProgress, CycleRead } from '@/types/appraisalSetup'
import { appraisalPlugins } from './mountAppraisal'

const fact = (id: string): FactView => ({ source: 'board_cards', id, key: id.toUpperCase(), title: `Work ${id}`, url: null, verb: 'Shipped', done_at: '2026-11-14T10:00:00Z', private: false })

describe('check-in: what went well', () => {
  it('ticks work, opens a note box on ticked items, and shows five until asked for more', async () => {
    const { plugins } = await appraisalPlugins()
    const facts = ['a', 'b', 'c', 'd', 'e', 'f'].map(fact)
    const wrapper = mount(CheckInWorkStep, {
      global: { plugins: plugins as never[] },
      props: { facts, tags: { b: { goal_id: null, heading: null } }, goals: [], editable: true, manager: 'Ravi', month: 'November', legacy: [], notes: { b: 'Took 60 ms off' }, wentWell: '' },
    })
    expect(wrapper.text()).toContain('Ticked items and your notes go to Ravi.')
    // Ticked first, with its note open; the others offer one.
    expect(wrapper.findAll('.ci-work__item')[0].text()).toContain('B')
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('Took 60 ms off')
    expect(wrapper.findAll('.ci-work__item')).toHaveLength(5)
    await wrapper.findAll('button').find(b => b.text() === 'Show 1 more')!.trigger('click')
    expect(wrapper.findAll('.ci-work__item')).toHaveLength(6)
    await wrapper.findAll('input[type="checkbox"]')[1].setValue(true)
    expect(wrapper.emitted('tick')![0]).toEqual(['a', true])
  })

  it('shows others only what was ticked, read-only', async () => {
    const { plugins } = await appraisalPlugins()
    const wrapper = mount(CheckInWorkStep, {
      global: { plugins: plugins as never[] },
      props: { facts: [fact('a'), fact('b')], tags: { a: { goal_id: null, heading: null } }, goals: [], editable: false, manager: 'Ravi', month: 'November', legacy: [], notes: { a: 'Why it mattered' }, wentWell: 'Paired on UAT' },
    })
    expect(wrapper.findAll('.ci-work__item')).toHaveLength(1)
    expect(wrapper.text()).toContain('“Why it mattered”')
    expect(wrapper.find('textarea').exists()).toBe(false)
  })
})

describe('team queue', () => {
  it('gives each item one button to its page, and none to a note still waiting', async () => {
    const { plugins } = await appraisalPlugins()
    const wrapper = mount(TeamQueue, {
      global: { plugins: plugins as never[] },
      props: {
        items: [
          { kind: 'note', role: 'team', person_name: 'Arjun Mehta', cycle_name: null, due_on: '2026-11-11', late: true, target: 'feedback', target_id: 'f1', count: null },
          { kind: 'waiting_on_check_in', role: 'team', person_name: 'Maya Chen', cycle_name: null, due_on: null, late: false, target: 'feedback', target_id: 'f2', count: null },
        ],
      },
    })
    expect(wrapper.text()).toContain('To do · 1')
    expect(wrapper.text()).toContain("Write notes on Arjun Mehta's check-in")
    expect(wrapper.findAll('a').map(a => a.attributes('href'))).toEqual(['/appraisals/notes/f1'])
  })
})

describe('confirming a suggested goal', () => {
  it("shows the person's reason and the three answers", async () => {
    const { plugins } = await appraisalPlugins()
    const goal = {
      id: 'g1', position: null, title: 'Cut onboarding time', measure: 'median under 2 days', origin: 'employee_own', status: 'proposed',
      suggestion_basis: null, proposed_by_name: 'Sofia', added_mid_period: false, created_at: '2026-11-18T10:00:00Z', replaces: null,
      dismiss_reason: null, reword_note: null, why: null,
      history: [{ kind: 'created', by_name: 'Sofia', at: '2026-11-18T10:00:00Z', before: null, after: null, reason: 'Sales keeps raising this' }],
      actions: { accept: true, dismiss: true, ask_reword: true, edit: false, remove: false, suggest_change: false },
    } as Goal
    const wrapper = mount(ProposalCard, { global: { plugins: plugins as never[] }, props: { goal, who: 'Sofia', full: false } })
    expect(wrapper.text()).toContain("Sofia's reason“Sales keeps raising this”")
    expect(wrapper.findAll('button').map(b => b.text())).toEqual(['Confirm', 'Suggest a change', 'Not this quarter'])
    await wrapper.findAll('button')[2].trigger('click')
    expect(wrapper.emitted('decline')).toHaveLength(1)
  })
})

describe('cycle page', () => {
  it('offers to remind the late ones, and flags people with no manager', async () => {
    const { plugins } = await appraisalPlugins()
    const progress: CycleProgress = {
      people: [], feedback: 0, feedback_done: 0, managers_overdue: [], min_goals: 3, check_in_periods: [], note_periods: [],
      remind_count: 9, reminded_at: null,
    }
    const cycle = { id: 'c1', status: 'active', period_end: '2099-12-31', ack_due: '2100-01-29' } as CycleRead
    const readiness = { drafting: 'manual' as const, ai_note: null, in_scope: 40, no_primary_manager: [{ user_id: 'u', name: 'X' }, { user_id: 'v', name: 'Y' }], no_template: [], identity: [] }
    const wrapper = mount(CycleRunning, { global: { plugins: plugins as never[] }, props: { cycle, progress, readiness, busy: null } })
    expect(wrapper.text()).toContain('9 people are late')
    await wrapper.findAll('button').find(b => b.text() === 'Remind 9 people')!.trigger('click')
    expect(wrapper.emitted('remind')).toHaveLength(1)
    expect(wrapper.text()).toContain('2 people have no manager, so nobody can review them.')
  })
})
