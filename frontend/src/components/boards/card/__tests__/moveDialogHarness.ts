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

// Mounting "Move to another board" for a spec: the card SEO-14 on SEO,
// the boards I may pick (Ops and Product), and Ops with three stages. The
// spec mocks boardsApi (vi.mock hoists there) and sets the replies with
// ``moveDefaults``.

import { flushPromises, mount } from '@vue/test-utils'
import { AxiosError, AxiosHeaders } from 'axios'
import { vi } from 'vitest'
import { VSelect } from 'vuetify/components'
import { makeBoardItem, makeCard, makeDetail, makeStage } from '@/components/boards/__tests__/fixtures'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import CardMoveBoardDialog from '@/components/boards/card/CardMoveBoardDialog.vue'
import { boardsApi } from '@/services/boardsApi'
import type { BoardDetail, BoardPersonRead, CardSummary, StageRead } from '@/types/boards'

export const api = vi.mocked(boardsApi)
export const CARD = makeCard('14', { key: 'SEO-14', stage_id: 'src-doing', checklist_done: 1, checklist_total: 3 })
export const SOURCE = makeDetail({
  board: { ...makeDetail().board, key: 'SEO', name: 'SEO' },
  stages: [makeStage('src-doing', { name: 'Doing', category: 'in_progress' })],
})
export const target = (stages: StageRead[]): BoardDetail =>
  makeDetail({ board: { ...makeDetail().board, id: 'b2', key: 'OPS', name: 'Ops' }, stages })
export const OPS_STAGES = [
  makeStage('t-todo', { name: 'To do', position: 0, is_default: true }),
  makeStage('t-doing', { name: 'doing', category: 'in_progress', position: 1 }),
  makeStage('t-done', { name: 'Done', category: 'done', position: 2 }),
]

export const person = (id: string, name: string, role: BoardPersonRead['role']): BoardPersonRead => ({
  id, name, avatar_url: null, role, via: 'member', team_name: null,
})

/** The usual replies: my boards, Ops, and nobody on it. */
export function moveDefaults(): void {
  vi.resetAllMocks()
  api.list.mockResolvedValue({ items: [
    makeBoardItem('SEO'), makeBoardItem('OPS', { name: 'Ops' }), makeBoardItem('DES', { role: 'viewer' }),
    makeBoardItem('PDT', { role: 'admin', name: 'Product' }), { kind: 'delivery', name: 'Delivery', path: '/buds' },
  ] })
  api.get.mockResolvedValue(target(OPS_STAGES))
  api.people.mockResolvedValue({ items: [] })
  api.repos.mockResolvedValue({ items: [] })
}

export function refusal(status: number, data: Record<string, unknown>, headers: Record<string, string> = {}): AxiosError {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError('failed', String(status), config, null, { status, statusText: '', headers, config, data })
}

export async function openDialog(
  source: BoardDetail = SOURCE, card: CardSummary = CARD, people: BoardPersonRead[] = [],
) {
  const { plugins } = boardTestPlugins()
  const wrapper = mount(CardMoveBoardDialog, {
    global: { plugins: plugins as never[] },
    props: { modelValue: true, card, board: source, people, fixLabel: 'Open card' },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}
export type Dialog = Awaited<ReturnType<typeof openDialog>>
export const selects = (w: Dialog) => w.findAllComponents(VSelect)
export async function pick(w: Dialog, key: string) {
  selects(w)[0].vm.$emit('update:modelValue', key)
  await flushPromises()
}
export const button = (label: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('button')].find(b => b.textContent?.trim() === label)
export async function clickMove() {
  button('Move')?.click()
  await flushPromises()
}
export const text = () => document.body.textContent ?? ''
