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

// A card's checklist on its page: add, tick, edit, delete and reorder
// lines. Each shows at once and is put back if the server refuses it;
// ``onCount`` hears the new done/total after every change that lands.

import { computed, ref, type Ref } from 'vue'
import { boardCardApi } from '@/services/boardCardApi'
import type { ChecklistItem } from '@/types/boards'
import { extractApiError } from '@/utils/errors'

export interface CardRef {
  key: string
  number: number
}

export function useCardChecklist(card: Ref<CardRef | null>, onCount: (done: number, total: number) => void) {
  const items = ref<ChecklistItem[]>([])
  const loading = ref(false)
  const error = ref('')
  let seq = 0

  const done = computed(() => items.value.filter(i => i.done).length)
  const report = () => onCount(done.value, items.value.length)

  async function load(): Promise<void> {
    const c = card.value
    if (!c) return
    const mine = ++seq
    loading.value = true
    error.value = ''
    try {
      const list = await boardCardApi.checklist(c.key, c.number)
      if (mine === seq) items.value = list
    } catch (err) {
      if (mine === seq) error.value = extractApiError(err, "Couldn't load the checklist.")
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  /** Run a change with an optimistic list; put the old list back on failure. */
  async function change(next: ChecklistItem[], send: (c: CardRef) => Promise<void>, fallback: string): Promise<string | null> {
    const c = card.value
    if (!c) return null
    const before = items.value
    items.value = next
    try {
      await send(c)
      report()
      return null
    } catch (err) {
      items.value = before
      return extractApiError(err, fallback)
    }
  }

  async function add(text: string, group: string | null = null): Promise<string | null> {
    const c = card.value
    if (!c) return null
    try {
      items.value = [...items.value, await boardCardApi.addItem(c.key, c.number, text, group)]
      report()
      return null
    } catch (err) {
      return extractApiError(err, "Couldn't add the item. Try again.")
    }
  }

  function patch(item: ChecklistItem, body: Partial<Pick<ChecklistItem, 'text' | 'done'>>): Promise<string | null> {
    const next = items.value.map(i => (i.id === item.id ? { ...i, ...body } : i))
    return change(next, async c => {
      const saved = await boardCardApi.updateItem(c.key, c.number, item.id, body)
      items.value = items.value.map(i => (i.id === saved.id ? saved : i))
    }, "Couldn't save the item. Try again.")
  }

  const toggle = (item: ChecklistItem) => patch(item, { done: !item.done })
  const edit = (item: ChecklistItem, text: string) => patch(item, { text })

  function remove(item: ChecklistItem): Promise<string | null> {
    return change(
      items.value.filter(i => i.id !== item.id),
      c => boardCardApi.removeItem(c.key, c.number, item.id),
      "Couldn't delete the item. Try again.",
    )
  }

  /**
   * Move a line up (-1) or down (+1) past the next line of its own group;
   * the server gets the whole order.
   */
  function move(item: ChecklistItem, delta: -1 | 1): Promise<string | null> {
    const group = items.value.filter(i => i.group_name === item.group_name)
    const target = group[group.findIndex(i => i.id === item.id) + delta]
    const from = items.value.findIndex(i => i.id === item.id)
    if (!target || from < 0) return Promise.resolve(null)
    const to = items.value.findIndex(i => i.id === target.id)
    const next = [...items.value]
    next.splice(to, 0, ...next.splice(from, 1))
    return change(next, async c => {
      items.value = await boardCardApi.orderItems(c.key, c.number, next.map(i => i.id))
    }, "Couldn't reorder the checklist. Try again.")
  }

  return { items, loading, error, done, load, add, toggle, edit, remove, move }
}
