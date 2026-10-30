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

/**
 * The stage stepper over any ordered stages: a board's own stages, with
 * the other stages as buttons when the page lets you move there.
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import BUDStageStepper from '../BUDStageStepper.vue'

const STAGES = [
  { id: 's1', label: 'Backlog' },
  { id: 's2', label: 'Writing' },
  { id: 's3', label: 'Published' },
]
const stubs = { 'v-icon': true }

describe('BUDStageStepper with custom stages', () => {
  it('marks done, current and to-do stages by id', () => {
    const wrapper = mount(BUDStageStepper, { props: { stages: STAGES, currentId: 's2' }, global: { stubs } })
    const steps = wrapper.findAll('li')
    expect(steps.map(s => s.classes().find(c => c.startsWith('stage-stepper__step--')))).toEqual([
      'stage-stepper__step--done', 'stage-stepper__step--current', 'stage-stepper__step--todo',
    ])
    expect(steps[1].attributes('aria-current')).toBe('step')
    expect(wrapper.findAll('button')).toHaveLength(0)
  })

  it('offers the other stages as buttons when selectable', async () => {
    const wrapper = mount(BUDStageStepper, {
      props: { stages: STAGES, currentId: 's2', selectable: true },
      global: { stubs },
    })
    const buttons = wrapper.findAll('button')
    expect(buttons.map(b => b.attributes('aria-label'))).toEqual(['Move to Backlog (done)', 'Move to Published (upcoming)'])
    await buttons[1].trigger('click')
    expect(wrapper.emitted('select')).toEqual([['s3']])
  })
})
