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

/** The shared directory refetches once membership changes, and forgets the org on sign-out. */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const get = vi.hoisted(() => vi.fn())
vi.mock('@/services/api', () => ({ default: { get } }))

import { useMemberDirectory } from './useMemberDirectory'

const dana = { id: 'u1', name: 'Dana', email: 'dana@x.io' }
const eli = { id: 'u2', name: 'Eli', email: 'eli@x.io' }

function reply(data: unknown) {
  return { data }
}

beforeEach(() => {
  get.mockReset()
  useMemberDirectory().reset()
})

describe('useMemberDirectory', () => {
  it('loads once, then again only after a member change', async () => {
    const dir = useMemberDirectory()
    get.mockResolvedValueOnce(reply([dana])).mockResolvedValueOnce(reply([dana, eli]))
    await dir.ensureLoaded()
    await dir.ensureLoaded()
    expect(get).toHaveBeenCalledTimes(1)

    dir.markStale()
    await dir.ensureLoaded()
    expect(get).toHaveBeenCalledTimes(2)
    expect(dir.entries.value.map(e => e.id)).toEqual(['u1', 'u2'])
  })

  it('tries again on the next read after a failed refresh', async () => {
    const dir = useMemberDirectory()
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    get.mockResolvedValueOnce(reply([dana]))
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(reply([dana, eli]))
    await dir.ensureLoaded()
    dir.markStale()
    await dir.ensureLoaded()
    expect(dir.entries.value.map(e => e.id)).toEqual(['u1'])
    await dir.ensureLoaded()
    expect(get).toHaveBeenCalledTimes(3)
    expect(dir.entries.value.map(e => e.id)).toEqual(['u1', 'u2'])
  })

  it('drops a load that lands after sign-out', async () => {
    const dir = useMemberDirectory()
    let land!: (value: unknown) => void
    get.mockReturnValueOnce(new Promise(resolve => { land = resolve }))
    const loading = dir.ensureLoaded()
    dir.reset()
    land(reply([dana]))
    await loading
    expect(dir.entries.value).toEqual([])
    expect(dir.nameFor('u1')).toBe('u1')
  })
})
