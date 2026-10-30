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
    expect(await docs.save('notes', 'New')).toBeNull()
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
    expect(await docs.save('notes', 'Mine')).toBe('Someone saved a newer version.')
    expect(api.writeDoc).toHaveBeenCalledWith('OPS', 3, 'notes', 'Mine', null)
    await vi.waitFor(() => expect(docs.current.notes?.body_md).toBe('Theirs'))
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
