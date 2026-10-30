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

// A card's history rows, registered by event type for ActivityTimeline.
// Names come from the page: stages from the board, people from the
// member directory. Events that later work adds (handover, AI runs) read
// as a plain line until they get rows of their own.

import { CATEGORY_COLORS, DOC_NAMES } from '@/constants/boards'
import type { CardDocKind, CardEventRead, CardEventType, StageCategory } from '@/types/boards'
import {
  actor, plainRow, section, text, type ActivityPart, type ActivityRenderer, type ActivityRenderers, type ActivityRow,
} from '@/utils/activity'
import { wordList } from '@/utils/format'

export interface CardTimelineNames {
  stage: (id: string | null) => string
  person: (id: string) => string
}

/** Edited fields as the history says them. */
const FIELD_WORDS: Record<string, string> = {
  title: 'title',
  description_md: 'description',
  priority: 'priority',
  start_at: 'start date',
  due_at: 'due date',
  due_done: 'due status',
  labels: 'labels',
}

const strings = (value: unknown): string[] => (Array.isArray(value) ? value.map(String) : [])

export function cardTimelineRenderers(names: CardTimelineNames): ActivityRenderers<CardEventRead> {
  const who = (e: CardEventRead) => (e.actor_id ? names.person(e.actor_id) : e.actor_label)
  const people = (e: CardEventRead) => wordList(strings(e.detail.user_ids).map(names.person))
  const stage = (id: string | null, category: StageCategory | null): ActivityPart => ({
    kind: 'status',
    text: names.stage(id),
    color: category ? CATEGORY_COLORS[category] : 'muted',
  })
  const said = (words: string) => (e: CardEventRead) => plainRow(who(e), words)

  function docRow(e: CardEventRead): ActivityRow {
    const doc = DOC_NAMES[e.detail.kind as CardDocKind] ?? 'document'
    const from = e.detail.restored_from
    return {
      primary: [
        ...actor(who(e)),
        text(from ? `restored the ${doc} to v${String(from)}` : `saved the ${doc}`),
        { kind: 'note', text: `v${String(e.detail.version ?? '')}` },
      ],
    }
  }

  // Every event type the backend sends has a row: a new one fails the type check here.
  const byType: Record<CardEventType, ActivityRenderer<CardEventRead>> = {
    created: { icon: 'mdi-plus-circle', color: 'success', row: said('created this card') },
    imported: { icon: 'mdi-import', color: 'info', row: said('imported this card') },
    moved: {
      icon: 'mdi-swap-horizontal',
      color: 'primary',
      row: e => ({
        primary: [
          ...actor(who(e)), text('moved'), stage(e.from_stage_id, e.from_category), { kind: 'arrow' },
          stage(e.to_stage_id, e.to_category),
        ],
      }),
    },
    moved_board: { icon: 'mdi-swap-horizontal', color: 'primary', row: said('moved this card from another board') },
    edited: {
      icon: 'mdi-pencil',
      color: 'primary',
      row: e => ({
        primary: [...actor(who(e)), text('edited'), section(wordList(strings(e.detail.fields).map(f => FIELD_WORDS[f] ?? f)))],
      }),
    },
    assigned: {
      icon: 'mdi-account-check',
      color: 'primary',
      row: e => ({ primary: [...actor(who(e)), text('assigned'), section(people(e))] }),
    },
    unassigned: {
      icon: 'mdi-account-remove',
      color: 'muted',
      row: e => ({ primary: [...actor(who(e)), text('unassigned'), section(people(e))] }),
    },
    commented: { icon: 'mdi-comment-text', color: 'muted', row: said('commented') },
    archived: { icon: 'mdi-archive-outline', color: 'muted', row: said('archived this card') },
    restored: { icon: 'mdi-archive-arrow-up-outline', color: 'primary', row: said('restored this card') },
    doc_updated: { icon: 'mdi-file-document-edit-outline', color: 'primary', row: docRow },
    handed_over: { icon: 'mdi-truck-delivery-outline', color: 'primary', row: said('handed this card over to Delivery') },
    returned: { icon: 'mdi-keyboard-return', color: 'warning', row: said('sent this card back from Delivery') },
    delivered: { icon: 'mdi-check-all', color: 'success', row: () => plainRow(null, 'Delivered') },
    ai_run: { icon: 'mdi-robot', color: 'info', row: () => plainRow(null, 'AI ran on this card') },
  }
  return {
    byType,
    fallback: { icon: 'mdi-circle-small', color: 'muted', row: said('changed this card') },
  }
}
