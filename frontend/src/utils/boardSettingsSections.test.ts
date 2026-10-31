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

/** The settings section kept in the URL, and a draft that follows the board until edited. */
import { describe, expect, it } from 'vitest'
import { nextTick, ref } from 'vue'
import { useSettingsDraft } from '@/composables/useSettingsDraft'
import { sectionFrom, sectionPath } from '@/utils/boardSettingsSections'

describe('board settings sections', () => {
  it('reads the section from the URL, General for anything else', () => {
    expect(sectionFrom('stages')).toBe('stages')
    expect(sectionFrom('ai')).toBe('ai')
    expect(sectionFrom('automation')).toBe('general')
    expect(sectionFrom(undefined)).toBe('general')
  })

  it('links General without a query and the rest with one', () => {
    expect(sectionPath('OPS', 'general')).toBe('/boards/OPS/settings')
    expect(sectionPath('OPS', 'labels')).toBe('/boards/OPS/settings?section=labels')
  })
})

describe('useSettingsDraft', () => {
  it('follows the source while untouched and flags a conflict once edited', async () => {
    const source = ref({ name: 'Ops' })
    const form = useSettingsDraft(() => ({ ...source.value }))
    source.value = { name: 'Operations' }
    await nextTick()
    expect(form.draft.value).toEqual({ name: 'Operations' })
    expect(form.dirty.value).toBe(false)

    form.draft.value!.name = 'Mine'
    expect(form.dirty.value).toBe(true)
    source.value = { name: 'Theirs' }
    await nextTick()
    expect(form.conflict.value).toBe(true)
    expect(form.draft.value).toEqual({ name: 'Mine' })

    form.reset()
    expect(form.draft.value).toEqual({ name: 'Theirs' })
    expect(form.conflict.value).toBe(false)
    expect(form.dirty.value).toBe(false)
  })
})
