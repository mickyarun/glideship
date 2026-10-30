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

// A card's checklist on its page: add, tick, edit, delete, reorder and put
// back a deleted line. Each shows at once; a refusal undoes only the line
// it was about, so another line's change made meanwhile stays. Opening
// another card clears the list, and replies (or rollbacks) for the card
// left behind are dropped. ``onCount`` hears the new done/total after
// every change that lands.

import { computed, ref, watch, type Ref } from 'vue'
import { boardCardApi } from '@/services/boardCardApi'
import type { ChecklistItem } from '@/types/boards'
import { extractApiError } from '@/utils/errors'

export interface CardRef {
  key: string
  number: number
}

const idOf = (c: CardRef | null) => (c ? `${c.key}-${c.number}` : '')

export function useCardChecklist(card: Ref<CardRef | null>, onCount: (done: number, total: number) => void) {
  const items = ref<ChecklistItem[]>([])
  const loading = ref(false)
  const error = ref('')
  let seq = 0

  const done = computed(() => items.value.filter(i => i.done).length)
  const report = () => onCount(done.value, items.value.length)

  watch(() => idOf(card.value), () => {
    seq++
    items.value = []
    error.value = ''
  })

  async function load(): Promise<void> {
    const c = card.value
    if (!c) return
    const mine = ++seq
    loading.value = !items.value.length
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

  /**
   * Run a change: ``show`` applies it now, ``send`` saves it, ``undo`` takes
   * back just this change if the save fails. Nothing lands on another card.
   */
  async function change(show: () => void, send: (c: CardRef) => Promise<void>, undo: () => void, fallback: string) {
    const c = card.value
    if (!c) return null
    const here = () => idOf(card.value) === idOf(c)
    show()
    try {
      await send(c)
      if (here()) report()
      return null
    } catch (err) {
      if (here()) undo()
      return extractApiError(err, fallback)
    }
  }

  const swap = (id: string, next: (i: ChecklistItem) => ChecklistItem) =>
    (items.value = items.value.map(i => (i.id === id ? next(i) : i)))

  async function add(text: string, group: string | null = null): Promise<string | null> {
    const c = card.value
    if (!c) return null
    try {
      const item = await boardCardApi.addItem(c.key, c.number, text, group)
      if (idOf(card.value) !== idOf(c)) return null
      items.value = [...items.value, item]
      report()
      return null
    } catch (err) {
      return extractApiError(err, "Couldn't add the item. Try again.")
    }
  }

  function patch(item: ChecklistItem, body: Partial<Pick<ChecklistItem, 'text' | 'done'>>): Promise<string | null> {
    const before = Object.fromEntries(Object.keys(body).map(k => [k, item[k as keyof typeof body]]))
    return change(
      () => swap(item.id, i => ({ ...i, ...body })),
      async c => {
        const saved = await boardCardApi.updateItem(c.key, c.number, item.id, body)
        if (idOf(card.value) === idOf(c)) swap(saved.id, () => saved)
      },
      () => swap(item.id, i => ({ ...i, ...before })),
      "Couldn't save the item. Try again.",
    )
  }

  const toggle = (item: ChecklistItem) => patch(item, { done: !item.done })
  const edit = (item: ChecklistItem, text: string) => patch(item, { text })

  function remove(item: ChecklistItem): Promise<string | null> {
    const at = items.value.findIndex(i => i.id === item.id)
    return change(
      () => (items.value = items.value.filter(i => i.id !== item.id)),
      c => boardCardApi.removeItem(c.key, c.number, item.id),
      () => {
        if (items.value.some(i => i.id === item.id)) return
        const next = [...items.value]
        next.splice(Math.min(at, next.length), 0, item)
        items.value = next
      },
      "Couldn't delete the item. Try again.",
    )
  }

  /** Put a deleted line back where it was (it comes back as a new line). */
  async function restore(item: ChecklistItem, at: number): Promise<string | null> {
    const error = await add(item.text, item.group_name)
    const c = card.value
    if (error || !c) return error
    const added = items.value[items.value.length - 1]
    const ids = items.value.map(i => i.id).filter(id => id !== added.id)
    ids.splice(Math.min(at, ids.length), 0, added.id)
    return reorder(ids, added, at)
  }

  function reorder(ids: string[], item: ChecklistItem, from: number): Promise<string | null> {
    const byId = new Map(items.value.map(i => [i.id, i]))
    return change(
      () => (items.value = ids.map(id => byId.get(id)).filter((i): i is ChecklistItem => !!i)),
      async c => {
        const saved = await boardCardApi.orderItems(c.key, c.number, ids)
        if (idOf(card.value) === idOf(c)) items.value = saved
      },
      () => {
        // Put just this line back where it was.
        const next = items.value.filter(i => i.id !== item.id)
        next.splice(Math.min(from, next.length), 0, item)
        items.value = next
      },
      "Couldn't reorder the checklist. Try again.",
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
    const ids = items.value.map(i => i.id)
    ids.splice(ids.indexOf(target.id), 0, ...ids.splice(from, 1))
    return reorder(ids, item, from)
  }

  return { items, loading, error, done, load, add, toggle, edit, remove, restore, move }
}
