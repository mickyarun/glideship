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

// Mounting the Trello import wizard against mocked APIs. The spec mocks
// the modules (vi.mock is hoisted per file); this file holds what they
// share: mounting and finding things.

import { flushPromises, mount } from '@vue/test-utils'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import TrelloImportWizard from '@/components/boards/imports/TrelloImportWizard.vue'
import { useAuthStore } from '@/stores/auth'
import type { BoardDetail } from '@/types/boards'

export async function mountWizard(
  options: { permissions?: string[]; board?: BoardDetail | null; query?: Record<string, string> } = {},
) {
  const { plugins, router } = boardTestPlugins()
  useAuthStore().user = {
    id: 'me', org_id: 'org1', permissions: options.permissions ?? ['boards:view', 'boards:create'],
  } as never
  const query = options.query ?? {}
  await router.push(options.board
    ? { name: 'board-import', params: { key: options.board.board.key }, query }
    : { name: 'board-import-new', query })
  const wrapper = mount(TrelloImportWizard, {
    global: { plugins: plugins as never[] },
    props: { board: options.board ?? null },
    attachTo: document.body,
  })
  await flushPromises()
  return { wrapper, router }
}

export function button(text: string): HTMLButtonElement | undefined {
  return [...document.querySelectorAll('button')].find(b => b.textContent?.trim().startsWith(text))
}

export async function chooseFile(file = new File(['{}'], 'board.json', { type: 'application/json' })) {
  const input = document.querySelector<HTMLInputElement>('input[type="file"]')!
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  input.dispatchEvent(new Event('change'))
  await flushPromises()
}

export const pageText = () => document.body.textContent ?? ''

/** The error text Vuetify shows under the field labelled `label` (by aria-label). */
export function fieldError(label: string): string {
  const input = document.querySelector(`input[aria-label="${label}"]`)
  return input?.closest('.v-input')?.querySelector('.v-messages')?.textContent?.trim() ?? ''
}
