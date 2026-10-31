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

/** The New BUD form sends what it always has to createBUD, with the shared agent options. */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, ref } from 'vue'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

import { CREATE_STAGES } from '@/composables/useBudAgentOptions'
import { useBudCreateForm } from '@/composables/useBudCreateForm'
import { useAgentSkillsStore, type AgentSkill } from '@/stores/agentSkills'
import { useBUDStore } from '@/stores/bud'
import type { BUDDocument } from '@/types'

const skill = (id: string, agentType: AgentSkill['agentType'], isDefault: boolean) =>
  ({ id, agentType, isDefault, name: id, skillSlug: id }) as AgentSkill

describe('useBudCreateForm', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    push.mockReset()
  })

  it('creates the BUD with its title, description, skill picks, phases and priority, then opens it', async () => {
    useAgentSkillsStore().skills = [skill('d1', 'design', true), skill('d2', 'design', false)]
    const store = useBUDStore()
    const create = vi.spyOn(store, 'createBUD').mockResolvedValue({ id: 'new' } as BUDDocument)
    const open = ref(true)
    const form = useBudCreateForm(open)
    await nextTick()
    form.title.value = '  Saved filters '
    form.description.value = ' Let triage save filters. '
    form.priority.value = 'P1'
    form.agents.stageSkillPicks.value.design = 'd2'
    form.agents.autoGenerate.value.closed = false
    await form.submit()
    const phases = { ...Object.fromEntries(CREATE_STAGES.map(s => [s.value, true])), closed: false }
    expect(create).toHaveBeenCalledWith('Saved filters', 'Let triage save filters.', { design: 'd2' }, phases, 'P1')
    expect(open.value).toBe(false)
    expect(push).toHaveBeenCalledWith('/buds/new')
    expect(form.title.value).toBe('')
  })

  it('stays open with the error when the BUD is not created', async () => {
    const store = useBUDStore()
    vi.spyOn(store, 'createBUD').mockResolvedValue(null)
    store.error = 'Title taken'
    const open = ref(true)
    const form = useBudCreateForm(open)
    form.title.value = 'Saved filters'
    await form.submit()
    expect(form.error.value).toBe('Title taken')
    expect(open.value).toBe(true)
    expect(push).not.toHaveBeenCalled()
  })
})
