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
 * Entering a stage this tab doesn't know yet (made elsewhere a moment ago):
 * the server's checklist question is still asked and the move resent.
 */
import { describe, expect, it, vi } from 'vitest'
import { makeCard } from '@/components/boards/__tests__/fixtures'
import { useBoardFeedback } from '@/composables/useBoardFeedback'
import { useStageEntry } from '@/composables/useStageEntry'

describe('useStageEntry', () => {
  it("asks about the checklist the server found open, for a stage this tab doesn't know", async () => {
    const entry = useStageEntry({ stages: () => [], feedback: useBoardFeedback(), fixLabel: 'Open card', fix: vi.fn() })
    const send = vi.fn()
      .mockResolvedValueOnce({ error: 'Open.', refusal: { code: 'CHECKLIST_OPEN', open: 1, total: 2 } })
      .mockResolvedValueOnce({ error: null })
    const pending = entry.enter(makeCard('1', { key: 'OPS-1' }), 'new-stage', send)
    await vi.waitFor(() => expect(entry.confirm.asking.value).toBe(true))
    expect(entry.confirm.question.value).toBe('1 of 2 checklist items is still open. Move OPS-1 to that stage anyway?')
    entry.confirm.answer(true)
    expect(await pending).toEqual({ error: null })
    expect(send).toHaveBeenLastCalledWith(true)
  })
})
