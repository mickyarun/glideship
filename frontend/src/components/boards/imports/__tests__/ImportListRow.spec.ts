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

/** A list going into an existing stage fills the header's Stage name and Category cells. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import ImportListRow from '@/components/boards/imports/ImportListRow.vue'
import { stageChoice, type ListRow } from '@/utils/importMapping'

const STAGE = { id: 's2', name: 'Shipped', category: 'done' as const, position: 2 }
// The header row's cells: Trello list, (arrow), Becomes, Stage name, Category.
const STAGE_NAME = 3
const CATEGORY = 4

function cells(choice: ListRow['choice']) {
  const { plugins } = boardTestPlugins()
  const row: ListRow = {
    list: {
      id: 'l1', name: 'Done', closed: false, card_count: 4, archived_card_count: 0,
      suggested_name: 'Done', suggested_category: 'done', suggested_skip: false,
    },
    choice, name: 'Done', category: 'done',
  }
  const wrapper = mount(ImportListRow, {
    props: { row, stages: [STAGE], problem: null, nameMax: null },
    global: { plugins: plugins as never[] },
  })
  return wrapper.findAll('.list-row > *')
}

describe('ImportListRow', () => {
  it('puts an existing stage\'s name and category chip under their own headers', () => {
    const row = cells(stageChoice('s2'))
    expect(row).toHaveLength(5)
    expect(row[STAGE_NAME].text()).toBe('Shipped')
    expect(row[STAGE_NAME].find('.app-tag, .v-chip').exists()).toBe(false)
    expect(row[CATEGORY].text()).toBe('Done')
  })

  it('fills the same two cells for a new stage, and spans them for a skipped list', () => {
    expect(cells('new')).toHaveLength(5)
    const skipped = cells('skip')
    expect(skipped).toHaveLength(4)
    expect(skipped[STAGE_NAME].text()).toBe('Not imported')
    expect(skipped[STAGE_NAME].classes()).toContain('list-row__note--wide')
  })
})
