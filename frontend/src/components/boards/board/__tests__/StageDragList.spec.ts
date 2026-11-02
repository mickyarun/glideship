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
 * A stage's cards as a drag list. After a drop, SortableJS puts the card
 * back where it came from, at the end of the list; when that was the
 * stage's last card and the board then moves it away, the card must
 * leave the screen, not stay behind as a copy.
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { Fragment, defineComponent, h, nextTick, ref } from 'vue'
import StageDragList from '@/components/boards/board/StageDragList.vue'

const cards = ref<string[]>([])

// The columns' template: a keyed v-for of cards inside the list.
const Column = defineComponent({
  setup() {
    return () =>
      h(StageDragList, { items: cards.value, stageId: 's1', group: 'b1', enabled: true }, {
        default: () => [h(Fragment, null, cards.value.map(id => h('article', { key: id, 'data-card-id': id }, id)))],
      })
  },
})

const shown = (list: Element) => [...list.querySelectorAll('[data-card-id]')].map(e => e.textContent)

describe('StageDragList', () => {
  it('carries the stage and renders the cards it is given', async () => {
    cards.value = ['A-1', 'A-2']
    const wrapper = mount(Column, { attachTo: document.body })
    const list = wrapper.get('[data-stage-id="s1"]').element
    expect(shown(list)).toEqual(['A-1', 'A-2'])
    wrapper.unmount()
  })

  it('removes a stage\'s last card once it moves away, after the drag put it back', async () => {
    cards.value = ['A-1']
    const wrapper = mount(Column, { attachTo: document.body })
    const list = wrapper.get('[data-stage-id="s1"]').element
    // As vue-draggable-plus restores a dropped card: appended to the list.
    list.appendChild(list.querySelector('[data-card-id="A-1"]')!)

    cards.value = []
    await nextTick()

    expect(shown(list)).toEqual([])
    wrapper.unmount()
  })
})
