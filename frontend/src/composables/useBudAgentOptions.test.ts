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


import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import { nextTick, ref } from 'vue'
import { CREATE_STAGES, stagesFrom, useBudAgentOptions } from '@/composables/useBudAgentOptions'
import { useAgentSkillsStore, type AgentSkill } from '@/stores/agentSkills'

const skill = (id: string, agentType: AgentSkill['agentType'], isDefault: boolean) =>
  ({ id, agentType, isDefault, name: id, skillSlug: id }) as AgentSkill

describe('useBudAgentOptions', () => {
  it('starts every agent on with its default skill, and sends only a changed skill', async () => {
    setActivePinia(createPinia())
    useAgentSkillsStore().skills = [skill('d1', 'design', true), skill('d2', 'design', false)]
    const options = useBudAgentOptions(ref(true))
    await nextTick()
    expect(options.choices()).toEqual({
      phases: Object.fromEntries(CREATE_STAGES.map(s => [s.value, true])),
      overrides: undefined,
    })
    expect(options.skillsForStage('design').map(s => s.label)).toEqual(['d1 · default', 'd2'])
    options.stageSkillPicks.value.design = 'd2'
    options.autoGenerate.value.closed = false
    expect(options.choices().overrides).toEqual({ design: 'd2' })
    expect(options.choices().phases.closed).toBe(false)
  })

  it('leaves out and turns off the stages before a later start, and sums up the rest', async () => {
    setActivePinia(createPinia())
    useAgentSkillsStore().skills = [skill('d1', 'design', true), skill('d2', 'design', false)]
    const options = useBudAgentOptions(ref(true))
    await nextTick()
    expect(stagesFrom('design').map(s => s.value)).toEqual(['design', 'tech_arch', 'testing', 'closed'])
    expect(stagesFrom(undefined)).toEqual(CREATE_STAGES)
    expect(options.choices('design').phases).toMatchObject({ bud: false, design: true })
    expect(options.summary('design')).toBe('4 on, default skills')
    options.stageSkillPicks.value.design = 'd2'
    options.autoGenerate.value.testing = false
    expect(options.summary('design')).toBe('3 on, custom skills')
    expect(options.summary()).toBe('4 on, custom skills')
  })
})

