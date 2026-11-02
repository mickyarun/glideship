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
 * The open card's documents: saving builds on the version the edit
 * started from, a conflict reloads the newer text, restore makes a new
 * version, and replies for a card no longer open are dropped.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardCardApi', () => ({
  boardCardApi: { docs: vi.fn(), versions: vi.fn(), version: vi.fn(), writeDoc: vi.fn(), restoreDoc: vi.fn() },
}))

import { httpError } from '@/components/boards/__tests__/fixtures'
import { boardCardApi } from '@/services/boardCardApi'
import { useBoardCardDocsStore } from '@/stores/boardCardDocs'
import type { DocRead } from '@/types/boards'

const api = vi.mocked(boardCardApi)
const CARD = { key: 'OPS', number: 3 }
const doc = (version: number, body_md = `v${version}`): DocRead => ({
  id: `d${version}`, kind: 'notes', state: 'current', version, source: 'ui', created_by: null,
  created_at: '2026-10-01T00:00:00Z', body_md,
})

describe('boardCardDocs store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    api.docs.mockResolvedValue({ items: [doc(2)] })
    api.versions.mockResolvedValue({ items: [doc(2), doc(1)], next_before: null })
  })

  it('saves on top of the current version and keeps the history in step', async () => {
    const docs = useBoardCardDocsStore()
    await docs.open(CARD)
    await docs.loadVersions('notes')
    api.writeDoc.mockResolvedValue(doc(3, 'New'))
    expect(await docs.save('notes', 'New', 2)).toEqual({ error: null, conflict: false })
    expect(api.writeDoc).toHaveBeenCalledWith('OPS', 3, 'notes', 'New', 2)
    expect(docs.current.notes?.version).toBe(3)
    expect(api.versions).toHaveBeenCalledTimes(2)
    // The new version's text is known without another fetch.
    expect(await docs.versionText('notes', 3)).toBe('New')
    expect(api.version).not.toHaveBeenCalled()
  })

  it('starts a new document from no version, and reloads after a conflict', async () => {
    api.docs.mockResolvedValue({ items: [] })
    const docs = useBoardCardDocsStore()
    await docs.open(CARD)
    api.writeDoc.mockRejectedValue(httpError(409, 'Someone saved a newer version.'))
    api.docs.mockResolvedValue({ items: [doc(1, 'Theirs')] })
    expect(await docs.save('notes', 'Mine', null)).toEqual({ error: 'Someone saved a newer version.', conflict: true })
    expect(api.writeDoc).toHaveBeenCalledWith('OPS', 3, 'notes', 'Mine', null)
    expect(docs.current.notes?.body_md).toBe('Theirs')
  })

  it('saves on the version the edit started from, not the one current at save time', async () => {
    const docs = useBoardCardDocsStore()
    await docs.open(CARD)
    api.docs.mockResolvedValue({ items: [doc(3, 'Theirs')] })
    await docs.refresh('notes')
    api.writeDoc.mockRejectedValue(httpError(409, 'Changed'))
    await docs.save('notes', 'Mine', 2)
    expect(api.writeDoc).toHaveBeenCalledWith('OPS', 3, 'notes', 'Mine', 2)
  })

  it('drops an old version\'s text that lands after the card changed, and empties on sign-out', async () => {
    const docs = useBoardCardDocsStore()
    await docs.open(CARD)
    let finish: (value: DocRead) => void = () => {}
    api.version.mockReturnValueOnce(new Promise(resolve => (finish = resolve)))
    const pending = docs.versionText('notes', 1)
    await docs.open({ key: 'OPS', number: 4 })
    finish(doc(1, 'Old'))
    expect(await pending).toBeNull()
    docs.reset()
    expect(docs.card).toBeNull()
    expect(docs.current).toEqual({})
  })

  it('restores an old version as a new one', async () => {
    const docs = useBoardCardDocsStore()
    await docs.open(CARD)
    api.restoreDoc.mockResolvedValue({ ...doc(3, 'v1'), source: 'revert' })
    expect(await docs.restore('notes', 1)).toBeNull()
    expect(api.restoreDoc).toHaveBeenCalledWith('OPS', 3, 'notes', 1, 2)
    expect(docs.current.notes?.body_md).toBe('v1')
  })

  it('drops a reply for a card that is no longer open', async () => {
    let finish: (value: { items: DocRead[] }) => void = () => {}
    api.docs.mockReturnValueOnce(new Promise(resolve => (finish = resolve)))
    const docs = useBoardCardDocsStore()
    void docs.open(CARD)
    api.docs.mockResolvedValue({ items: [] })
    await docs.open({ key: 'OPS', number: 4 })
    finish({ items: [doc(9)] })
    await Promise.resolve()
    expect(docs.current.notes).toBeUndefined()
  })
})
