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

// Mounting board components in jsdom: Vuetify, a fresh Pinia, and a memory
// router that knows the board routes by name.

import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

vi.stubGlobal('ResizeObserver', class { observe(): void {} unobserve(): void {} disconnect(): void {} })
// Vuetify menus position against the visual viewport, which jsdom lacks.
if (!('visualViewport' in window)) {
  vi.stubGlobal('visualViewport', Object.assign(new EventTarget(), { width: 1024, height: 768, scale: 1, offsetLeft: 0, offsetTop: 0 }))
}

const blank = { render: () => null }

export function boardTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: blank },
      { path: '/boards', name: 'boards', component: blank },
      { path: '/boards/:key', name: 'board', component: blank },
      { path: '/boards/imports/trello', name: 'board-import-new', component: blank },
      { path: '/boards/:key/settings', name: 'board-settings', component: blank },
      { path: '/boards/:key/metrics', name: 'board-metrics', component: blank },
      { path: '/boards/:key/settings/import', name: 'board-import', component: blank },
      { path: '/boards/:key/cards/:number', name: 'board-card', component: blank },
      { path: '/buds', component: blank },
      { path: '/garden', name: 'garden', component: blank },
      { path: '/settings/qa-automation', name: 'settings-qa-automation', component: blank },
      { path: '/members', name: 'members', component: blank },
    ],
  })
}

export function boardTestPlugins(): { pinia: Pinia; router: Router; plugins: unknown[] } {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = boardTestRouter()
  return { pinia, router, plugins: [createVuetify({ components, directives }), pinia, router] }
}
