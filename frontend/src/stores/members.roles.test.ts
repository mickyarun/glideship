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
 * Loading roles: the page and the role dialog share one load, and a refresh
 * after a role change isn't undone by an older reply landing late.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/api', () => ({ default: { get: vi.fn() } }))

import api from '@/services/api'
import { useMembersStore } from '@/stores/members'

const get = vi.mocked(api.get)
const replies: Array<(value: unknown) => void> = []

const role = (name: string) => ({ id: name, name, scope_type: 'custom', permissions: [] })

beforeEach(() => {
  setActivePinia(createPinia())
  replies.length = 0
  get.mockReset()
  get.mockImplementation(() => new Promise(ok => { replies.push(ok) }))
})

describe('roles', () => {
  it('joins a load already running instead of starting another', async () => {
    const store = useMembersStore()
    const page = store.fetchRoles()
    const dialog = store.ensureRoles()
    expect(get).toHaveBeenCalledTimes(1)
    replies[0]({ data: [role('qa')] })
    await Promise.all([page, dialog])
    expect(store.roles.map(r => r.name)).toEqual(['qa'])

    await store.ensureRoles()
    expect(get).toHaveBeenCalledTimes(1)
  })

  it('keeps the newer list when an older reply lands last', async () => {
    const store = useMembersStore()
    const older = store.fetchRoles()
    const newer = store.fetchRoles()
    replies[1]({ data: [role('qa'), role('release captain')] })
    await newer
    replies[0]({ data: [role('qa')] })
    await older
    expect(store.roles.map(r => r.name)).toEqual(['qa', 'release captain'])
  })
})
