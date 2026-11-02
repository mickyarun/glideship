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

/** Editing one markdown text through the caller's save callback. */
import { describe, expect, it, vi } from 'vitest'

import { useMarkdownSection } from '@/composables/useMarkdownSection'

describe('useMarkdownSection', () => {
  it('starts from the saved text and saves only a change', async () => {
    const save = vi.fn().mockResolvedValue(undefined)
    const md = useMarkdownSection(() => 'Saved', save)
    md.toggle()
    expect(md.editValue.value).toBe('Saved')
    await md.save()
    expect(save).not.toHaveBeenCalled()
    expect(md.editing.value).toBe(false)
    md.toggle()
    md.editValue.value = 'Changed'
    await md.save()
    expect(save).toHaveBeenCalledWith('Changed')
    expect(md.editing.value).toBe(false)
  })

  it('stays open with the draft when the save reports failure', async () => {
    const md = useMarkdownSection(() => '', vi.fn().mockResolvedValue(false))
    md.toggle()
    md.editValue.value = 'Draft'
    await md.save()
    expect(md.editing.value).toBe(true)
    expect(md.editValue.value).toBe('Draft')
  })
})
