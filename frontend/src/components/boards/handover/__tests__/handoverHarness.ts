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

// Mounting the handover dialog for a spec: SEO-14 on SEO, whose handover
// stage is Done and whose BUDs land at design by default, the org's agent
// skills already loaded, and the usual preview and result. The spec mocks
// services/handoverApi (vi.mock hoists there) and sets replies with
// ``handoverDefaults``.

import { flushPromises, mount } from '@vue/test-utils'
import { AxiosError, AxiosHeaders } from 'axios'
import { vi } from 'vitest'
import { makeCard, makeCardDetail, makeDetail, makeStage } from '@/components/boards/__tests__/fixtures'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import HandoverDialog from '@/components/boards/handover/HandoverDialog.vue'
import { handoverApi } from '@/services/handoverApi'
import { useAgentSkillsStore, type AgentSkill } from '@/stores/agentSkills'
import type { CardSummary, HandoverPreview, HandoverRead, HandoverResult } from '@/types/boards'

export const api = vi.mocked(handoverApi)
export const CARD = makeCard('14', { key: 'SEO-14', number: 14, stage_id: 'doing', priority: 'P1', has_description: true })
export const BOARD = makeDetail({
  board: { ...makeDetail().board, key: 'SEO', handover_enabled: true, handover_stage_id: 'done', handover_target_status: 'design' },
  stages: [makeStage('doing', { name: 'Doing', category: 'in_progress' }), makeStage('done', { name: 'Ready for dev', category: 'done' })],
  capabilities: [...makeDetail().capabilities, 'hand_over'],
})

export const PREVIEW: HandoverPreview = {
  mode: 'create', target_status: 'design', title: 'Saved filters', requirements_md: 'Triage leads **rebuild** filters.',
  figma_url: null, priority: 'P1', impacted_repos: [{ repo_id: 'r1', repo_name: 'web' }],
  similar: [{ bud_id: 'b118', key: 'BUD-118', title: 'Remember filters', status: 'design', distance: 0.2 }],
  warnings: [], reopens: null,
}

export function handover(over: Partial<HandoverRead> = {}): HandoverRead {
  return {
    id: 'h1', card_id: CARD.id, status: 'active', linked_existing: false, target_status: 'design', bud_id: 'b123',
    bud_key: 'BUD-123', bud_title: 'Saved filters', bud_status: 'design', can_open_bud: true, handed_over_by: 'u1',
    handed_over_at: '2026-10-31T10:00:00Z', returned_at: null, return_reason: null, stage_start_failed: false, history: [], ...over,
  }
}

export const RESULT: HandoverResult = {
  handover: handover(), card: makeCardDetail('14', { key: 'SEO-14', stage_id: 'done' }), design_available: false,
}

const skill = (id: string, agentType: AgentSkill['agentType'], isDefault: boolean) =>
  ({ id, agentType, isDefault, name: `Skill ${id}`, skillSlug: id }) as AgentSkill

export function handoverDefaults(): void {
  vi.resetAllMocks()
  api.preview.mockResolvedValue(PREVIEW)
  api.confirm.mockResolvedValue(RESULT)
  api.buds.mockResolvedValue([])
}

export function refusal(status: number, data: Record<string, unknown>): AxiosError {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError('failed', String(status), config, null, { status, statusText: '', headers: {}, config, data })
}

export async function openDialog(card: CardSummary = CARD, over: { holdsLive?: boolean; canLink?: boolean } = {}) {
  const { plugins } = boardTestPlugins()
  useAgentSkillsStore().skills = [skill('prd-1', 'bud', true), skill('design-1', 'design', true), skill('design-2', 'design', false)]
  const wrapper = mount(HandoverDialog, {
    global: { plugins: plugins as never[] },
    props: {
      modelValue: true, card, board: BOARD, holdsLive: over.holdsLive ?? false, heldBudIds: [],
      canLink: over.canLink ?? true, docMax: null,
    },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}
export type Dialog = Awaited<ReturnType<typeof openDialog>>

export const button = (label: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('button')].find(b => b.textContent?.trim() === label)
export async function click(label: string): Promise<void> {
  const found = button(label)
  if (!found) throw new Error(`No button "${label}"`)
  found.click()
  await flushPromises()
}
export const text = () => document.body.textContent ?? ''
/** The body of the nth confirm sent. */
export const sent = (n = 0) => api.confirm.mock.calls[n][2]
