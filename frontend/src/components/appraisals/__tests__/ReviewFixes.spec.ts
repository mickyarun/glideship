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

/** Goal boxes that clear, notes that tick, "Looks fair", and a change the manager suggested. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CheckInGoalsStep from '@/components/appraisals/CheckInGoalsStep.vue'
import CheckInWorkStep from '@/components/appraisals/CheckInWorkStep.vue'
import FairnessLookList from '@/components/appraisals/FairnessLookList.vue'
import GoalCard from '@/components/appraisals/GoalCard.vue'
import ShareResultButton from '@/components/appraisals/ShareResultButton.vue'
import type { Goal } from '@/types/appraisalGoals'
import type { LookItem } from '@/utils/appraisalFairness'
import { appraisalPlugins } from './mountAppraisal'

const NONE = { accept: false, dismiss: false, ask_reword: false, edit: false, remove: false, suggest_change: false }

describe('check-in boxes', () => {
  it('clears a goal value the person emptied, and leaves untouched boxes alone', async () => {
    const { plugins } = await appraisalPlugins()
    const goals = [
      { id: 'g1', position: 1, title: 'Fewer reopened bugs', measure: 'Under 5%', value: '7%', source_note: null, source_url: null },
      { id: 'g2', position: 2, title: 'Ship refunds', measure: null, value: 'Live', source_note: null, source_url: null },
    ]
    const wrapper = mount(CheckInGoalsStep, { global: { plugins: plugins as never[] }, props: { goals, month: 'November', editable: true, previous: {} } })
    const [first, second] = wrapper.findAll('textarea')
    await first.setValue('')
    await first.trigger('blur')
    await second.trigger('blur')
    expect(wrapper.emitted('save')).toEqual([['g1', '']])
  })

  it('ticks an item when the person writes a note on it', async () => {
    const { plugins } = await appraisalPlugins()
    const fact = { source: 'board_cards', id: 'a', key: 'A-1', title: 'Retry backoff', url: null, verb: 'Shipped', done_at: null, private: false }
    const wrapper = mount(CheckInWorkStep, {
      global: { plugins: plugins as never[] },
      props: { facts: [fact], tags: {}, goals: [], editable: true, manager: 'Ravi', month: 'November', legacy: [], notes: {}, wentWell: '' },
    })
    await wrapper.find('.ci-work__add').trigger('click')
    await wrapper.find('textarea').setValue('Found the timeout')
    expect(wrapper.emitted('tick')).toEqual([['a', true]])
  })
})

describe('fairness: needs a look', () => {
  const item = (over: Partial<LookItem>): LookItem => ({
    key: 'k1', title: 'Tom Becker · Daniel Okafor', detail: 'Two steps apart.', tag: 'Big difference', appraisalId: 'a1',
    managerName: 'Daniel Okafor', fairIds: ['a1'], fairBy: null, fairAt: null, canSendBack: true, ...over,
  })

  it('offers send back and looks fair until marked, then says who looked', async () => {
    const { plugins } = await appraisalPlugins()
    const marked = item({ key: 'k2', fairBy: 'Hana People', fairAt: '2027-01-20T10:00:00Z' })
    const wrapper = mount(FairnessLookList, { global: { plugins: plugins as never[] }, props: { items: [item({}), marked], busy: null } })
    expect(wrapper.text()).toContain('Needs a look · 1')
    const buttons = wrapper.findAll('button').map(b => b.text())
    expect(buttons).toEqual(['Send back to Daniel', 'Looks fair'])
    await wrapper.findAll('button')[1].trigger('click')
    expect(wrapper.emitted('fair')?.[0]).toEqual([item({})])
    expect(wrapper.text()).toContain('Looks fair · Hana People, Wed 20 Jan 2027')
    expect(wrapper.find('a').text()).toBe('Open review for Tom Becker · Daniel Okafor')
  })
})

describe('a change the manager suggested', () => {
  const change: Goal = {
    id: 'g2', position: null, title: 'Fewer reopened bugs', measure: 'Under 5%', origin: 'manager_added', status: 'proposed',
    suggestion_basis: null, proposed_by_name: 'Daniel', added_mid_period: false, created_at: '2026-11-05T10:00:00Z', replaces: 'g1',
    from_manager: true, dismiss_reason: null, reword_note: null, why: null, history: [], actions: { ...NONE, accept: true, dismiss: true },
  }

  it('is the person to take or turn down', async () => {
    const { plugins } = await appraisalPlugins()
    const wrapper = mount(GoalCard, { global: { plugins: plugins as never[] }, props: { goal: change, managerName: 'Daniel', asEmployee: true } })
    expect(wrapper.text()).toContain('Daniel suggested this change.')
    expect(wrapper.findAll('button').map(b => b.text())).toEqual(['Take this change', 'Not this one'])
  })

  it('waits on the person when the manager looks at it', async () => {
    const { plugins } = await appraisalPlugins()
    const goal = { ...change, actions: { ...NONE, dismiss: true, edit: true } }
    const wrapper = mount(GoalCard, { global: { plugins: plugins as never[] }, props: { goal, managerName: 'Daniel', asEmployee: false } })
    expect(wrapper.text()).toContain('A change you suggested, waiting for them to take it.')
    expect(wrapper.findAll('button').map(b => b.text())).toEqual(['Edit', 'Take it back'])
  })
})

describe('sharing one result', () => {
  // The dialog itself is AppConfirmDialog's to test; here, what it says and when sharing happens.
  const AppConfirmDialog = {
    props: ['modelValue', 'body'],
    emits: ['confirm'],
    template: '<div v-if="modelValue"><p class="body">{{ body }}</p><button class="ok" @click="$emit(\'confirm\')">ok</button></div>',
  }

  it('says so when the fairness check holds it back, and shares only once confirmed', async () => {
    const { plugins } = await appraisalPlugins()
    for (const held of [true, false]) {
      const wrapper = mount(ShareResultButton, {
        global: { plugins: plugins as never[], stubs: { AppConfirmDialog } },
        props: { name: 'Eli Employee', held, busy: false },
      })
      await wrapper.find('button').trigger('click')
      expect(wrapper.find('.body').text().includes('This result is held back in the fairness check.')).toBe(held)
      expect(wrapper.emitted('share')).toBeUndefined()
      await wrapper.find('.ok').trigger('click')
      expect(wrapper.emitted('share')).toHaveLength(1)
    }
  })
})
