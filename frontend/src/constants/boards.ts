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

// UI choices for team boards. Lengths, caps and page sizes are the
// server's: read them from GET /boards/limits (stores/boards.ts), never here.

import type { BoardRole, BoardVisibility, CardDocKind, CardDocSource, LabelColor, StageCategory } from '@/types/boards'
import type { HandoverTarget } from '@/types/boards/settings'

/** The sidebar lists up to this many starred boards… */
export const SIDEBAR_STARRED_LIMIT = 7
/** …or, with nothing starred, this many recently opened ones. */
export const SIDEBAR_RECENT_LIMIT = 5

/** Pressed anywhere outside a text field, opens the board switcher. */
export const SWITCHER_SHORTCUT_KEY = 'b'

/**
 * How many letters of a new board's name the suggested key takes, before
 * it's clamped to the server's key length (GET /boards/limits).
 */
export const KEY_SUGGESTION_LENGTH = 4

/** Filter changes are saved to the board's prefs once they settle this long. */
export const PREFS_SAVE_DELAY_MS = 800

export const CATEGORY_LABELS: Record<StageCategory, string> = {
  todo: 'To do',
  in_progress: 'In progress',
  done: 'Done',
  canceled: 'Canceled',
}

/** Theme colour names (plugins/boardThemeColors.ts). */
export const CATEGORY_COLORS: Record<StageCategory, string> = {
  todo: 'category-todo',
  in_progress: 'category-in-progress',
  done: 'category-done',
  canceled: 'category-canceled',
}

export function labelColor(color: LabelColor): string {
  return `label-${color}`
}

export const ROLE_LABELS: Record<BoardRole, string> = {
  viewer: 'Viewer',
  editor: 'Editor',
  admin: 'Admin',
}

/** "You're an editor", for a board's header. */
export function rolePhrase(role: BoardRole): string {
  return role === 'viewer' ? "You're a viewer" : `You're an ${ROLE_LABELS[role].toLowerCase()}`
}

export const VISIBILITY_LABELS: Record<BoardVisibility, { icon: string; text: string }> = {
  org: { icon: 'mdi-domain', text: 'Org-visible' },
  members: { icon: 'mdi-lock-outline', text: 'Members only' },
}

/** Every stage category, in board order. */
export const STAGE_CATEGORIES = Object.keys(CATEGORY_LABELS) as StageCategory[]

/** Label colours in swatch order (the server's `BoardLabelColor`). */
export const LABEL_COLORS: LabelColor[] = [
  'green', 'yellow', 'orange', 'red', 'purple', 'blue', 'sky', 'lime', 'pink', 'black',
]

/** Board roles, lowest first. */
export const BOARD_ROLES = Object.keys(ROLE_LABELS) as BoardRole[]

/** Where a handed-over card's BUD lands by default, as board settings name it. */
export const HANDOVER_TARGETS: { value: HandoverTarget; label: string }[] = [
  { value: 'bud', label: 'Requirements' },
  { value: 'design', label: 'Design' },
  { value: 'tech_arch', label: 'Tech arch' },
]

/** On touch screens a card must be held this long before it drags, so the column still scrolls. */
export const DRAG_TOUCH_DELAY_MS = 150
/** How long a drag's slide animation runs. */
export const DRAG_ANIMATION_MS = 150

/** A card's documents, in the order its Documents tab lists them. */
export const DOC_LABELS: Record<CardDocKind, string> = {
  prd: 'PRD',
  design_brief: 'Design brief',
  notes: 'Notes',
}
export const DOC_KINDS = Object.keys(DOC_LABELS) as CardDocKind[]

/** Where a document version came from, for its history. */
export const DOC_SOURCE_LABELS: Record<CardDocSource, { text: string; color: string }> = {
  ui: { text: 'edit', color: 'primary' },
  mcp: { text: 'mcp', color: 'brand' },
  agent: { text: 'ai', color: 'success' },
  migration: { text: 'import', color: 'muted' },
  revert: { text: 'restore', color: 'warning' },
}
