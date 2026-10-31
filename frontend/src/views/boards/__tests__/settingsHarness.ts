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

// Mounting a board's settings the way the app does: the route shell with
// the settings as its child page, a fresh Pinia, a signed-in person and
// Vuetify at a chosen width. Each spec mocks the APIs and the socket.

import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { h } from 'vue'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@/components/boards/__tests__/mountHelpers'
import { EDITOR_CAPS, makeDetail, makeStage } from '@/components/boards/__tests__/fixtures'
import { useAuthStore } from '@/stores/auth'
import type { BoardAction, BoardDetail, BoardLimits } from '@/types/boards'
import BoardShell from '@/views/boards/BoardShell.vue'
import BoardSettingsView from '@/views/boards/BoardSettingsView.vue'

const blank = { render: () => null }

export const ADMIN_CAPS: BoardAction[] = [
  ...EDITOR_CAPS, 'review_draft', 'run_agent', 'edit_settings', 'manage_stages', 'manage_members',
  'manage_labels', 'configure_agents', 'import', 'archive_board', 'remove_any_attachment',
]
/** What an admin may do on an archived board. */
export const ARCHIVED_ADMIN_CAPS: BoardAction[] = ['view', 'archive_board']

/** An admin's view of a board with To do (default), Doing, Done and Canceled stages. */
export function adminDetail(over: Partial<BoardDetail> = {}): BoardDetail {
  return makeDetail({
    role: 'admin',
    capabilities: ADMIN_CAPS,
    stages: [
      makeStage('s1', { name: 'To do', category: 'todo', position: 0, is_default: true }),
      makeStage('s2', { name: 'Doing', category: 'in_progress', position: 1, open_cards: 3 }),
      makeStage('s3', { name: 'Done', category: 'done', position: 2 }),
      makeStage('s4', { name: 'Dropped', category: 'canceled', position: 3 }),
    ],
    ...over,
  })
}

export const LIMITS = {
  board_name_max: 150, board_description_max: 5000, stage_name_max: 60, max_stages: 8,
  wip_limit_max: 999, label_name_max: 40,
} as BoardLimits

export async function mountSettings(
  path = '/boards/OPS/settings',
  { width = 1280, permissions = ['boards:view'] }: { width?: number; permissions?: string[] } = {},
) {
  window.innerWidth = width
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().user = { id: 'me', org_id: 'org1', permissions } as never
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: blank },
      { path: '/boards', name: 'boards', component: blank },
      {
        path: '/boards/:key',
        component: BoardShell,
        children: [
          { path: '', name: 'board', component: blank },
          { path: 'settings', name: 'board-settings', component: BoardSettingsView },
          { path: 'settings/import', name: 'board-import', component: blank },
        ],
      },
    ],
  })
  await router.push(path)
  const vuetify = createVuetify({ components, directives })
  const wrapper = mount({ render: () => h(RouterView) }, {
    global: { plugins: [vuetify, pinia, router] },
    attachTo: document.body,
  })
  await flushPromises()
  return { wrapper, router }
}

/** A button anywhere on the page (dialogs render outside the wrapper), by its text or label. */
export function button(name: string): HTMLButtonElement {
  const hit = [...document.querySelectorAll<HTMLButtonElement>('button')].find(
    b => b.getAttribute('aria-label') === name || b.textContent?.trim() === name,
  )
  if (!hit) throw new Error(`No button "${name}"`)
  return hit
}

/** An input by its aria-label. */
export function input(label: string): HTMLInputElement {
  const hit = document.querySelector<HTMLInputElement>(`input[aria-label="${label}"]`)
  if (!hit) throw new Error(`No input "${label}"`)
  return hit
}

/** Type into an input and leave it, as someone tabbing away would. */
export async function typeAndLeave(field: HTMLInputElement, value: string): Promise<void> {
  field.value = value
  field.dispatchEvent(new Event('input'))
  field.dispatchEvent(new Event('blur'))
  await flushPromises()
}
