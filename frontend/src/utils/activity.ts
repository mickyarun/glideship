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

// What an activity timeline row says, as data: each event type registers
// a renderer (its dot's icon and colour, and a function from the event to
// its row), so a BUD's history and a card's history share one timeline
// (components/common/ActivityTimeline.vue) without a v-if per event type.

/** One piece of a row's line. */
export type ActivityPart =
  | { kind: 'actor' | 'text' | 'section' | 'note'; text: string; tone?: 'error' }
  | { kind: 'status'; text: string; color: string }
  | { kind: 'arrow' }
  | { kind: 'badge'; text: string; color?: string; variant?: 'tonal' | 'outlined'; icon?: string; title?: string }
  | { kind: 'icon'; icon: string; color: string }
  | { kind: 'link'; text: string; href: string }

export interface ActivityRow {
  /** The main line. */
  primary: ActivityPart[]
  /** Badges or details under it. */
  meta?: ActivityPart[]
  /** Extra lines of small text under it. */
  lines?: string[]
  tone?: 'error'
}

export interface ActivityRenderer<E> {
  icon: string
  color: string
  row: (event: E) => ActivityRow
}

/** Renderers by event type, and the one for types nobody registered. */
export interface ActivityRenderers<E> {
  byType: Record<string, ActivityRenderer<E>>
  fallback: ActivityRenderer<E>
}

/** Every event a timeline lists has an id and a time. */
export interface ActivityEvent {
  id: string
  created_at: string
}

export const actor = (name: string | null | undefined): ActivityPart[] =>
  name ? [{ kind: 'actor', text: name }] : []
export const text = (value: string, tone?: 'error'): ActivityPart => ({ kind: 'text', text: value, tone })
export const section = (value: string): ActivityPart => ({ kind: 'section', text: value })

/** "{actor} {words}": the row for events with nothing more to say. */
export function plainRow(name: string | null | undefined, words: string): ActivityRow {
  return { primary: [...actor(name), text(words)] }
}

export function rendererFor<E>(renderers: ActivityRenderers<E>, type: string): ActivityRenderer<E> {
  return renderers.byType[type] ?? renderers.fallback
}
