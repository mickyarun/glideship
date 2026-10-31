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

// A board's stage agents as its AI settings edit them: every stage's list,
// the org's skills to pick from (the board skills suggested first), and
// each change (add, switch on or off, change the trigger, reorder, remove)
// saved at once by replacing that stage's list. Agents already on the stage
// go back with their ids, so they stay the same agents (their runs and Retry
// keep pointing at them); an added one has none. Orders follow the list's
// positions, so two agents never share one; the UI offers "when a card
// enters" to one agent per stage, and the server refuses a second (422)
// in words the section shows. Another admin's change reloads that stage.
// Nothing is saved over a stage whose list never loaded (that would wipe
// agents the page never saw), and a reply older than the stage's latest
// (a slow GET behind a newer PUT) is dropped.

import { computed, ref, watch } from 'vue'
import type { BoardPage } from '@/composables/useBoardPage'
import type { BoardSettingsStatus } from '@/composables/useBoardSettingsStatus'
import { useTopicChannel } from '@/composables/useTopicChannel'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { boardTopic, type BoardSkillOption, type BoardSocketMessage, type StageAgentRead, type StageAgentWrite } from '@/types/boards'
import { extractApiError } from '@/utils/errors'
import { logFailure } from '@/utils/logFailure'

/** A stage's list, loaded or not. */
interface StageList {
  items: StageAgentRead[]
  loading: boolean
  error: string
  /** The list came back (from a GET or a save) at least once, and its last GET didn't fail. */
  loaded: boolean
}

const NOT_LOADED = "This stage's AI didn't load, so nothing was saved. Load it again and retry."

/** A refusal in the page's own words, shaped like a server reply so the section shows it. */
const refusal = (detail: string) => Object.assign(new Error(detail), { response: { data: { detail } } })

/** What a change sets on an agent (``id`` when it's already on the stage); its order is its position in the list. */
export type AgentEdit = Pick<StageAgentRead, 'skill_id' | 'trigger' | 'enabled'> & { id?: string }

/** An agent as the list sends it, at its position. */
const toWrite = (a: AgentEdit, order: number): StageAgentWrite => ({
  ...(a.id ? { id: a.id } : {}), skill_id: a.skill_id, trigger: a.trigger, enabled: a.enabled, order,
})

export function useStageAgents(page: BoardPage, status: BoardSettingsStatus, allowed: () => boolean) {
  const lists = ref<Record<string, StageList>>({})
  const skills = ref<BoardSkillOption[]>([])
  const skillsError = ref('')
  const skillsLoading = ref(false)
  const key = computed(() => page.board.detail.value?.board.key ?? '')
  /** Each stage's latest request; an older reply is dropped. */
  const latest: Record<string, number> = {}
  const next = (stageId: string) => (latest[stageId] = (latest[stageId] ?? 0) + 1)
  const stages = computed(() => page.board.detail.value?.stages ?? [])

  /** Suggested skills first, then the rest of the library by name. */
  const sortedSkills = computed(() =>
    [...skills.value].sort((a, b) => Number(b.suggested) - Number(a.suggested) || a.name.localeCompare(b.name)),
  )

  async function loadStage(stageId: string): Promise<void> {
    const k = key.value
    if (!k || !allowed()) return
    const mine = next(stageId)
    const held = lists.value[stageId]
    lists.value[stageId] = { items: held?.items ?? [], loading: true, error: '', loaded: held?.loaded ?? false }
    const current = () => k === key.value && mine === latest[stageId]
    try {
      const items = await boardSettingsApi.stageAgents(k, stageId)
      if (current()) lists.value[stageId] = { items, loading: false, error: '', loaded: true }
    } catch (err) {
      logFailure('boards', 'stage agents fetch', err)
      if (current()) {
        lists.value[stageId] = { items: [], loading: false, error: extractApiError(err, "Couldn't load this stage's AI."), loaded: false }
      }
    }
  }

  /** The stage's list is in hand, so a change can build on it. */
  const ready = (stageId: string) => !!lists.value[stageId]?.loaded && !lists.value[stageId]?.error

  async function loadSkills(): Promise<void> {
    const k = key.value
    if (!k || !allowed()) return
    skillsLoading.value = true
    skillsError.value = ''
    try {
      skills.value = await boardSettingsApi.skills(k)
    } catch (err) {
      logFailure('boards', 'board skills fetch', err)
      skillsError.value = extractApiError(err, "Couldn't load your organization's skills.")
    } finally {
      skillsLoading.value = false
    }
  }

  /**
   * Save a stage's whole list, built by ``edit`` from the list as it stands
   * when this change's turn comes (after any change still on its way), so
   * quick changes build on each other; the reply replaces what's shown.
   * A stage whose list isn't loaded is never saved.
   */
  function save(stageId: string, edit: (items: StageAgentRead[]) => AgentEdit[], done: string): Promise<boolean> {
    if (!ready(stageId)) return Promise.resolve(false)
    return status.run(
      async k => {
        if (!ready(stageId)) throw refusal(NOT_LOADED)
        const body = edit(lists.value[stageId].items).map(toWrite)
        const mine = next(stageId)
        const items = await boardSettingsApi.putStageAgents(k, stageId, body)
        if (mine === latest[stageId]) lists.value[stageId] = { items, loading: false, error: '', loaded: true }
      },
      done,
      { refresh: false, fallback: "Couldn't save the stage's AI. Try again." },
    )
  }

  /** Switch the board's AI on or off. */
  function setEnabled(on: boolean): Promise<boolean> {
    return status.run(
      async k => page.board.replace(await boardSettingsApi.update(k, { ai_enabled: on })),
      on ? 'Turned AI on for this board' : 'Turned AI off for this board',
      { refresh: false },
    )
  }

  const topic = computed(() => (page.board.detail.value ? boardTopic(page.board.detail.value.board.id) : null))
  useTopicChannel<BoardSocketMessage>(
    topic,
    { stage_agents_changed: message => void loadStage(message.stage_id) },
    () => stages.value.forEach(s => void loadStage(s.id)),
    { ignoreOwn: true },
  )

  // Every stage the board has (a new stage too); a stage that went away drops out.
  watch(() => stages.value.map(s => s.id).join(), () => {
    const ids = new Set(stages.value.map(s => s.id))
    lists.value = Object.fromEntries(Object.entries(lists.value).filter(([id]) => ids.has(id)))
    for (const id of ids) if (!lists.value[id]) void loadStage(id)
  }, { immediate: true })
  // Becoming an admin (or the board coming back from the archive) loads them.
  watch(allowed, can => {
    if (can) stages.value.forEach(s => void loadStage(s.id))
  })

  return { lists, skills: sortedSkills, skillsError, skillsLoading, ready, loadSkills, loadStage, save, setEnabled }
}

export type StageAgents = ReturnType<typeof useStageAgents>
