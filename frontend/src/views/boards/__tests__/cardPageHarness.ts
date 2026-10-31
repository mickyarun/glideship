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

// Mounting a card's page the way the app does: the board route shell with
// the card as its child page, a fresh Pinia, and Vuetify at a chosen width.

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { h } from 'vue'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@/components/boards/__tests__/mountHelpers'
import BoardCardView from '@/views/boards/BoardCardView.vue'
import BoardShell from '@/views/boards/BoardShell.vue'

const blank = { render: () => null }

export async function mountCardPage(path = '/boards/OPS/cards/3', { width = 1280 } = {}) {
  window.innerWidth = width
  const pinia = createPinia()
  setActivePinia(pinia)
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
          { path: 'settings', name: 'board-settings', component: blank },
          { path: 'settings/import', name: 'board-import', component: blank },
          { path: 'cards/:number', name: 'board-card', component: BoardCardView },
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

/** The buttons whose text includes ``text``. */
export function buttonsWith(wrapper: Pick<VueWrapper, 'findAll'>, text: string) {
  return wrapper.findAll('button').filter(b => b.text().includes(text))
}
