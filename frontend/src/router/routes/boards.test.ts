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

/** The Delivery board's key typed as a board address opens the BUD board. */
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { boardRoutes } from '@/router/routes/boards'

const blank = { render: () => null }

function router() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: blank, children: boardRoutes },
      { path: '/buds', name: 'buds', component: blank },
    ],
  })
}

describe('board routes', () => {
  it('redirects /boards/BUD, in any case, to the Delivery board', async () => {
    for (const path of ['/boards/BUD', '/boards/bud']) {
      const r = router()
      await r.push(path)
      expect(r.currentRoute.value.fullPath).toBe('/buds')
    }
  })

  it('still opens team boards by key', () => {
    expect(router().resolve('/boards/OPS').name).toBe('board')
    expect(router().resolve('/boards/OPS/settings').name).toBe('board-settings')
  })

  it('imports into a new board with boards:create, and into a board from its settings', () => {
    const fresh = router().resolve('/boards/imports/trello')
    expect(fresh.name).toBe('board-import-new')
    expect(fresh.meta.permission).toBe('boards:create')
    expect(router().resolve('/boards/OPS/settings/import').name).toBe('board-import')
  })
})
