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
 * The open card's documents (PRD, design brief, notes): each one's current
 * version, the AI draft waiting for review (the newest per kind), its
 * history a page at a time, old versions' text, and the last change made
 * elsewhere. Saving writes a new version on top of the one the edit started
 * from; a 409 (someone saved in between) reloads the documents. Replies for
 * a card no longer open are dropped; it empties when the page closes or I sign out.
 */
import { isAxiosError } from 'axios'
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

import type { CardRef } from '@/composables/useCardChecklist'
import { boardCardApi } from '@/services/boardCardApi'
import { useAuthStore } from '@/stores/auth'
import type { CardDocKind, CardDocState, DocRead, DocVersionRead } from '@/types/boards'
import { extractApiError } from '@/utils/errors'

interface History {
  items: DocVersionRead[]
  next: number | null
  loading: boolean
  loaded: boolean
}

const emptyHistory = (): History => ({ items: [], next: null, loading: false, loaded: false })

/** A change made elsewhere, as the board's channel told it: what it made, and who. */
export interface DocChange {
  state: CardDocState
  actor: string | null
}

/** A save's outcome: the error to show, and whether someone saved a newer version first. */
export interface WriteResult {
  error: string | null
  conflict: boolean
}

export const useBoardCardDocsStore = defineStore('boardCardDocs', () => {
  const card = ref<CardRef | null>(null)
  const current = ref<Partial<Record<CardDocKind, DocRead>>>({})
  const drafts = ref<Partial<Record<CardDocKind, DocRead>>>({})
  const history = ref<Partial<Record<CardDocKind, History>>>({})
  /** The last change to each document made elsewhere (to say what became of a draft). */
  const changes = ref<Partial<Record<CardDocKind, DocChange>>>({})
  const loading = ref(false)
  const error = ref('')
  const texts = new Map<string, string>()
  let seq = 0
  /** The open card's documents came back once; later reloads keep what's shown (and any editor) up. */
  let loaded = false

  const same = (c: CardRef, mine: number) => mine === seq && card.value?.key === c.key && card.value.number === c.number

  async function loadDocs(): Promise<void> {
    const c = card.value
    if (!c) return
    const mine = seq
    loading.value = !loaded
    try {
      const list = await boardCardApi.docs(c.key, c.number)
      if (!same(c, mine)) return
      current.value = Object.fromEntries(list.items.map(d => [d.kind, d]))
      // Newest first, so the first of each kind is the one waiting (a newer one retires the rest).
      drafts.value = Object.fromEntries([...(list.drafts ?? [])].reverse().map(d => [d.kind, d]))
      for (const d of list.items) texts.set(`${d.kind}:${d.version}`, d.body_md)
      loaded = true
      error.value = ''
    } catch (err) {
      if (same(c, mine)) error.value = extractApiError(err, "Couldn't load the card's documents.")
    } finally {
      if (same(c, mine)) loading.value = false
    }
  }

  /** Nothing held for any card. */
  function clear(): void {
    current.value = {}
    drafts.value = {}
    history.value = {}
    changes.value = {}
    error.value = ''
    texts.clear()
  }

  /** Forget the open card's documents. */
  function reset(): void {
    seq++
    loaded = false
    card.value = null
    loading.value = false
    clear()
  }
  watch(() => useAuthStore().token, token => {
    if (!token) reset()
  })

  /** Start on a card: nothing loaded, then its current documents. */
  function open(next: CardRef): Promise<void> {
    seq++
    loaded = false
    card.value = next
    clear()
    return loadDocs()
  }

  /** The first page of a document's versions, or the next with ``more``. */
  async function loadVersions(kind: CardDocKind, { more = false } = {}): Promise<void> {
    const c = card.value
    const held = history.value[kind] ?? emptyHistory()
    if (!c || held.loading || (more && !held.next)) return
    const mine = seq
    history.value[kind] = { ...held, loading: true }
    try {
      const page = await boardCardApi.versions(c.key, c.number, kind, more ? held.next : null)
      if (!same(c, mine)) return
      const items = more ? [...held.items, ...page.items] : page.items
      history.value[kind] = { items, next: page.next_before, loading: false, loaded: true }
    } catch (err) {
      if (!same(c, mine)) return
      history.value[kind] = { ...held, loading: false }
      error.value = extractApiError(err, "Couldn't load the document's history.")
    }
  }

  /** One version's text, fetched once. */
  async function versionText(kind: CardDocKind, version: number): Promise<string | null> {
    const c = card.value
    const cached = texts.get(`${kind}:${version}`)
    if (cached !== undefined || !c) return cached ?? null
    const mine = seq
    try {
      const doc = await boardCardApi.version(c.key, c.number, kind, version)
      if (!same(c, mine)) return null
      texts.set(`${kind}:${version}`, doc.body_md)
      return doc.body_md
    } catch (err) {
      if (same(c, mine)) error.value = extractApiError(err, "Couldn't load that version.")
      return null
    }
  }

  /** A document got a new version (here, or elsewhere as ``change``): reload what's shown of it. */
  async function refresh(kind: CardDocKind, change?: DocChange): Promise<void> {
    if (change) changes.value = { ...changes.value, [kind]: change }
    await loadDocs()
    if (history.value[kind]?.loaded) await loadVersions(kind)
  }

  /** Send a write that returns the document's new current version (a 409 reloads the documents). */
  async function write(kind: CardDocKind, send: (c: CardRef) => Promise<DocRead>, fallback: string): Promise<WriteResult> {
    const c = card.value
    if (!c) return { error: null, conflict: false }
    const mine = seq
    try {
      const doc = await send(c)
      if (!same(c, mine)) return { error: null, conflict: false }
      current.value = { ...current.value, [kind]: doc }
      texts.set(`${kind}:${doc.version}`, doc.body_md)
      if (history.value[kind]?.loaded) void loadVersions(kind)
      return { error: null, conflict: false }
    } catch (err) {
      const conflict = isAxiosError(err) && err.response?.status === 409
      if (same(c, mine) && conflict) await refresh(kind)
      return { error: extractApiError(err, fallback), conflict }
    }
  }

  /**
   * Save ``body`` as the document's new current version, on top of ``base``:
   * the version the edit started from (null for a document not written yet).
   */
  function save(kind: CardDocKind, body: string, base: number | null): Promise<WriteResult> {
    return write(kind, c => boardCardApi.writeDoc(c.key, c.number, kind, body, base), "Couldn't save the document. Try again.")
  }

  /** Make an old version's text current again, as a new version on top of the current one. */
  async function restore(kind: CardDocKind, version: number): Promise<string | null> {
    const base = current.value[kind]?.version ?? null
    const result = await write(
      kind,
      c => boardCardApi.restoreDoc(c.key, c.number, kind, version, base),
      "Couldn't restore that version. Try again.",
    )
    return result.error
  }

  return {
    card, current, drafts, history, changes, loading, error,
    open, reset, loadDocs, loadVersions, versionText, refresh, write, save, restore,
  }
})
