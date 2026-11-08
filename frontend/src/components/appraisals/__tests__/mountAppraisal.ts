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

// Mounting appraisal screens in jsdom: Vuetify, a fresh Pinia, and a memory
// router that knows the appraisal routes by name.

import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

// Vuetify's auto-grow textareas watch their size, which jsdom can't.
vi.stubGlobal('ResizeObserver', class { observe(): void {} unobserve(): void {} disconnect(): void {} })

const blank = { render: () => null }
const NAMES: [string, string][] = [
  ['/appraisals', 'appraisal-my-month'],
  ['/appraisals/team', 'appraisal-team'],
  ['/appraisals/check-ins/:id', 'appraisal-check-in'],
  ['/appraisals/feedback/:id', 'appraisal-feedback'],
  ['/appraisals/cycles', 'appraisal-cycles'],
  ['/appraisals/cycles/:id', 'appraisal-cycle'],
  ['/appraisals/settings', 'appraisal-settings'],
  ['/appraisals/role-templates', 'appraisal-role-templates'],
  ['/appraisals/goals/:id', 'appraisal-goals'],
  ['/appraisals/review', 'appraisal-my-review'],
  ['/appraisals/reviews/:id', 'appraisal-review'],
]

export async function appraisalPlugins(start = '/'): Promise<{ pinia: Pinia; router: Router; plugins: unknown[] }> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: blank }, ...NAMES.map(([path, name]) => ({ path, name, component: blank }))],
  })
  await router.push(start)
  return { pinia, router, plugins: [createVuetify({ components, directives }), pinia, router] }
}
