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

/** The filter bar's timing: restore quietly, debounce the search, save once, never drop a save. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'

vi.mock('@/services/boardsApi', () => ({ boardsApi: { savePrefs: vi.fn() } }))

import { PREFS_SAVE_DELAY_MS } from '@/constants/boards'
import { SEARCH_DELAY_MS } from '@/composables/useDebounced'
import { boardsApi } from '@/services/boardsApi'
import { useBoardFilters } from './useBoardFilters'

const save = vi.mocked(boardsApi.savePrefs)
const SAVED = { q: 'seo', assignee_ids: [], label_ids: [], priorities: [], repo_ids: [], archived: false }

function setup() {
  const apply = vi.fn()
  const scope = effectScope()
  const f = scope.run(() => useBoardFilters(apply))!
  return { f, apply, scope }
}

describe('useBoardFilters', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    save.mockReset().mockResolvedValue({ starred: false, filters: SAVED })
  })
  afterEach(() => vi.useRealTimers())

  it('restores saved filters without applying or saving them', () => {
    const { f, apply, scope } = setup()
    expect(f.restore('OPS', SAVED)).toMatchObject({ query: 'seo' })
    expect(f.filters.value.query).toBe('seo')
    vi.runAllTimers()
    expect(apply).not.toHaveBeenCalled()
    expect(save).not.toHaveBeenCalled()
    scope.stop()
  })

  it('applies a pick at once but waits for typing to settle', () => {
    const { f, apply, scope } = setup()
    f.restore('OPS', null)
    f.filters.value = { ...f.filters.value, priority: 'P1' }
    vi.advanceTimersByTime(0)
    expect(apply).toHaveBeenLastCalledWith(expect.objectContaining({ priority: 'P1' }))
    f.filters.value = { ...f.filters.value, query: 's' }
    f.filters.value = { ...f.filters.value, query: 'se' }
    vi.advanceTimersByTime(SEARCH_DELAY_MS - 1)
    expect(apply).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(1)
    expect(apply).toHaveBeenLastCalledWith(expect.objectContaining({ query: 'se' }))
    scope.stop()
  })

  it('saves once, after the changes settle', () => {
    const { f, scope } = setup()
    f.restore('OPS', null)
    f.filters.value = { ...f.filters.value, query: 'a' }
    f.filters.value = { ...f.filters.value, query: 'ab' }
    vi.advanceTimersByTime(PREFS_SAVE_DELAY_MS)
    expect(save).toHaveBeenCalledOnce()
    expect(save).toHaveBeenCalledWith('OPS', expect.objectContaining({ q: 'ab' }))
    scope.stop()
  })

  it('sends a pending save for the board I leave, not the next one', () => {
    const { f, scope } = setup()
    f.restore('OPS', null)
    f.filters.value = { ...f.filters.value, label: 'l1' }
    f.restore('SEO', SAVED)
    expect(save).toHaveBeenCalledWith('OPS', expect.objectContaining({ label_ids: ['l1'] }))
    vi.runAllTimers()
    expect(save).toHaveBeenCalledOnce()
    scope.stop()
  })

  it('saves the repository filter with the rest, and restores it', () => {
    const { f, scope } = setup()
    f.restore('OPS', null)
    f.filters.value = { ...f.filters.value, repo: 'r1' }
    vi.advanceTimersByTime(PREFS_SAVE_DELAY_MS)
    expect(save).toHaveBeenCalledWith('OPS', expect.objectContaining({ repo_ids: ['r1'] }))
    expect(f.restore('OPS', { ...SAVED, repo_ids: ['r2'] }).repo).toBe('r2')
    scope.stop()
  })

  it('sends a pending save when the page goes away', () => {
    const { f, scope } = setup()
    f.restore('OPS', null)
    f.filters.value = { ...f.filters.value, archived: true }
    scope.stop()
    expect(save).toHaveBeenCalledWith('OPS', expect.objectContaining({ archived: true }))
  })

  it('logs a failed save and carries on', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    save.mockRejectedValue(new Error('offline'))
    const { f, scope } = setup()
    f.restore('OPS', null)
    f.filters.value = { ...f.filters.value, query: 'x' }
    vi.advanceTimersByTime(PREFS_SAVE_DELAY_MS)
    // The message only, never the error object (its request can carry a token).
    await vi.waitFor(() => expect(error).toHaveBeenCalledWith('[boards] prefs save failed:', 'offline'))
    error.mockRestore()
    scope.stop()
  })

  it('clearing keeps the archived view', () => {
    const { f, scope } = setup()
    f.restore('OPS', { ...SAVED, archived: true })
    f.clear()
    expect(f.filters.value).toMatchObject({ query: '', archived: true })
    scope.stop()
  })
})
