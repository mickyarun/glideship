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

// Which stage agents a new BUD runs and with which skill, the same in the
// New BUD form and the handover dialog. Every stage's agent starts on (the
// learning recap included: it feeds the estimator), and each stage is
// pre-filled with that agent's current default skill so the form shows what
// would run if nothing changes. Only non-default picks are sent, so the BUD
// keeps following whatever the org marks as default later. A BUD that
// starts later than requirements (a handover landing at design) never runs
// the stages before it: they're left out of the form and sent as off.

import { computed, ref, watch, type Ref } from 'vue'
import { useAgentSkillsStore, type AgentSkill, type AgentType } from '@/stores/agentSkills'
import type { BUDStatus } from '@/types'

/** A stage whose agent can be switched on and given a skill at creation. */
export interface CreateStage {
  value: BUDStatus
  label: string
  agentType: AgentType
}

export interface StageSkillOption {
  id: string
  label: string
}

// Mirrors BUD_STAGE_AGENT_TYPE in backend/app/agents/skill_mapping.py. If a
// new stage gets an agent on the backend, add it here too.
export const CREATE_STAGES: readonly CreateStage[] = [
  { value: 'bud', label: 'PRD writer', agentType: 'bud' },
  { value: 'design', label: 'Design', agentType: 'design' },
  { value: 'tech_arch', label: 'Tech plan', agentType: 'techPlan' },
  { value: 'testing', label: 'Test plan', agentType: 'testPlan' },
  { value: 'closed', label: 'Learning recap', agentType: 'learning' },
]

export interface AgentChoices {
  /** Every stage, on or off. */
  phases: Record<string, boolean>
  /** Only the stages whose skill isn't the default; undefined when none. */
  overrides: Record<string, string> | undefined
}

/** The stages from ``from`` on (every stage when it isn't one of them). */
export function stagesFrom(from?: BUDStatus): readonly CreateStage[] {
  const at = CREATE_STAGES.findIndex(s => s.value === from)
  return at > 0 ? CREATE_STAGES.slice(at) : CREATE_STAGES
}

export function useBudAgentOptions(open: Ref<boolean>) {
  const skillsStore = useAgentSkillsStore()
  const stageSkillPicks = ref<Record<string, string | null>>({})
  const autoGenerate = ref<Record<string, boolean>>({})
  const skillsLoading = computed(() => skillsStore.loading)

  function skillsForStage(agentType: AgentType): StageSkillOption[] {
    return skillsStore.skills
      .filter((s): s is AgentSkill & { id: string } => s.agentType === agentType && s.id !== null)
      .map(s => ({ id: s.id, label: s.isDefault ? `${s.name} · default` : s.name }))
  }

  function defaultSkillId(agentType: AgentType): string | null {
    return skillsStore.skills.find(s => s.agentType === agentType && s.isDefault)?.id ?? null
  }

  /**
   * Every stage's agent on, unless the person already chose. Runs the moment
   * the dialog opens, not after the skills load: a switch that shows "off"
   * while they load and then turns itself on would run an agent the person
   * saw as off and left alone.
   */
  function defaultAgentsOn(): void {
    for (const stage of CREATE_STAGES) {
      if (autoGenerate.value[stage.value] === undefined) autoGenerate.value[stage.value] = true
    }
  }

  function prefillSkills(): void {
    for (const stage of CREATE_STAGES) {
      stageSkillPicks.value[stage.value] = defaultSkillId(stage.agentType)
    }
  }

  function reset(): void {
    stageSkillPicks.value = {}
    autoGenerate.value = {}
  }

  watch(open, async isOpen => {
    if (!isOpen) return
    defaultAgentsOn()
    if (skillsStore.skills.length === 0 && !skillsStore.loading) await skillsStore.fetchSkills()
    prefillSkills()
  }, { immediate: true })

  // Skills that land after the dialog opened (slow network) still prefill.
  watch(() => skillsStore.skills.length, () => {
    if (open.value) prefillSkills()
  })

  const customSkill = (stage: CreateStage) => {
    const picked = stageSkillPicks.value[stage.value]
    return !!picked && picked !== defaultSkillId(stage.agentType)
  }

  /** What a BUD starting at ``from`` runs; earlier stages are off. */
  function choices(from?: BUDStatus): AgentChoices {
    const shown = stagesFrom(from)
    const overrides: Record<string, string> = {}
    const phases: Record<string, boolean> = {}
    for (const stage of CREATE_STAGES) {
      const on = shown.includes(stage) && !!autoGenerate.value[stage.value]
      phases[stage.value] = on
      if (shown.includes(stage) && customSkill(stage)) overrides[stage.value] = stageSkillPicks.value[stage.value] as string
    }
    return { phases, overrides: Object.keys(overrides).length > 0 ? overrides : undefined }
  }

  /** "4 on, default skills", for a folded agents section. */
  function summary(from?: BUDStatus): string {
    const shown = stagesFrom(from)
    const on = shown.filter(s => autoGenerate.value[s.value]).length
    const skills = shown.some(s => autoGenerate.value[s.value] && customSkill(s)) ? 'custom skills' : 'default skills'
    return `${on} on, ${skills}`
  }

  return { stageSkillPicks, autoGenerate, skillsLoading, skillsForStage, choices, summary, reset }
}

export type BudAgentOptions = ReturnType<typeof useBudAgentOptions>
