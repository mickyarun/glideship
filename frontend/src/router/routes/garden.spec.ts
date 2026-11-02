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

/**
 * Garden access: engineers or board users may enter (any one permission),
 * engineers keep their dashboard garden, and nobody else gets in.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { BOARDS_VIEW, GARDEN_PERMISSIONS, WORKSPACE_ENGINEERING } from '@/utils/workspace'
import { installGuards, resetSetupCache } from '@/router/guards'
import router from '@/router'
import { gardenRoutes } from './garden'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(async () => ({ data: { is_setup_complete: true } })) },
}))

const Stub = { template: '<div />' }

function makeRouter(): Router {
  const r = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: Stub },
      { path: '/dashboard', name: 'dashboard', component: Stub, meta: { workspace: 'engineering' } },
      { path: '/boards', name: 'boards', component: Stub },
      { path: '/leave', name: 'leave', component: Stub },
      { path: '/', component: Stub, children: gardenRoutes.map(route => ({ ...route, component: Stub }) as RouteRecordRaw) },
    ],
  })
  installGuards(r)
  return r
}

function signInWith(permissions: string[]): void {
  localStorage.setItem('bodhiorchard_token', 'token')
  const auth = useAuthStore()
  auth.user = { permissions, has_boards: true } as unknown as typeof auth.user
}

describe('Garden routes', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    resetSetupCache()
  })

  it('ask for either engineering or boards:view, on the Garden and the character picker', () => {
    expect(GARDEN_PERMISSIONS).toEqual([WORKSPACE_ENGINEERING, BOARDS_VIEW])
    for (const name of ['garden', 'character-select']) {
      const meta = router.resolve({ name }).meta
      expect(meta.permission).toEqual([WORKSPACE_ENGINEERING, BOARDS_VIEW])
      expect(meta.workspace).toBeUndefined()
    }
  })

  it('opens the Garden page for a board user outside engineering', async () => {
    signInWith([BOARDS_VIEW])
    const r = makeRouter()
    await r.push('/garden')
    expect(r.currentRoute.value.name).toBe('garden')
  })

  it('sends an engineer to the dashboard garden', async () => {
    signInWith([WORKSPACE_ENGINEERING, BOARDS_VIEW])
    const r = makeRouter()
    await r.push('/garden')
    expect(r.currentRoute.value.fullPath).toBe('/dashboard?view=garden')
  })

  it('keeps out someone with neither', async () => {
    signInWith([])
    const r = makeRouter()
    await r.push('/garden')
    expect(r.currentRoute.value.name).toBe('leave')
  })
})
