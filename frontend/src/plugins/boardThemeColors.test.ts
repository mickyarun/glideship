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

/** Every board colour exists in both themes, and the themes carry them. */
import { describe, expect, it } from 'vitest'
import { glideshipDark, glideshipLight } from './vuetify-theme'
import { boardColorsDark, boardColorsLight } from './boardThemeColors'
import { CATEGORY_COLORS, labelColor } from '@/constants/boards'

describe('board theme colours', () => {
  it('has the same keys in dark and light', () => {
    expect(Object.keys(boardColorsDark).sort()).toEqual(Object.keys(boardColorsLight).sort())
  })

  it('covers every stage category and label colour the UI asks for', () => {
    const labels = ['green', 'yellow', 'orange', 'red', 'purple', 'blue', 'sky', 'lime', 'pink', 'black'] as const
    const wanted = [...Object.values(CATEGORY_COLORS), ...labels.map(labelColor)]
    for (const theme of [glideshipDark, glideshipLight]) {
      for (const name of wanted) expect(theme.colors?.[name], name).toMatch(/^#[0-9A-F]{6}$/i)
    }
  })
})
