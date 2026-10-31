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

/**
 * Board key lengths until GET /boards/limits answers: BOARD_KEY_MIN_LENGTH
 * and BOARD_KEY_MAX_LENGTH in backend/app/services/boards/constants.py.
 */
export const BOARD_KEY_LENGTHS = { min: 2, max: 10 }

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

/** What each landing means for the new BUD, under the dialog's stage choice. */
export const HANDOVER_TARGET_NOTES: Record<HandoverTarget, string> = {
  bud: 'The PRD writer starts from what the card has.',
  design: 'Requirements are marked done, credited to you. Only the Design agent runs.',
  tech_arch: 'Requirements and design are marked done, credited to you. Only the Tech plan agent runs.',
}
/**
 * A similar BUD this close (cosine distance) reads as a "close match"; the
 * rest of the preview's list, up to its cut-off, as "possible". Mirrors
 * THRESHOLD_AUTO_SKIP in backend/app/services/jira_dedup.py.
 */
export const HANDOVER_CLOSE_MATCH_DISTANCE = 0.25
/** A card tile names this many of its BUDs; more show as the "1 of 3 in prod" roll-up. */
export const BUD_CHIPS_SHOWN = 2
/** How many BUDs the link picker lists at once; typing narrows them. */
export const HANDOVER_LINK_RESULTS_MAX = 8
/** ``?handover=1`` on a card's page opens its handover dialog (the board's card menu sends it). */
export const HANDOVER_QUERY_KEY = 'handover'
/** Starting words for a send-back's reason, one tap each. */
export const SEND_BACK_REASONS = ['Unclear scope', 'Duplicate', 'Not now'] as const
/**
 * A send-back's reason, as the card comment holds it. Mirrors
 * HANDOVER_RETURN_REASON_MAX_CHARS in backend/app/services/boards/constants.py.
 */
export const SEND_BACK_REASON_MAX = 9_900
/** How many of the origin card's comments a BUD's Origin panel shows per page. */
export const ORIGIN_COMMENTS_PAGE = 5

/** On touch screens a card must be held this long before it drags, so the column still scrolls. */
export const DRAG_TOUCH_DELAY_MS = 150
/** How long a drag's slide animation runs (none when the OS asks for reduced motion). */
export const DRAG_ANIMATION_MS = 150
/** How far a press must travel before it drags, so a slightly shaky click still opens the card. */
export const DRAG_START_TOLERANCE_PX = 4

/** How long the board's snackbar stays (one with a refusal waits to be dismissed). */
export const TOAST_MS = 6000
/** How long the fields a stage needs stay highlighted after "Open card" or "Show me". */
export const FIELD_HIGHLIGHT_MS = 2500
/** How often, and how many times, the card page looks for a field still drawing (a document loading). */
export const FIELD_FOCUS_RETRY_MS = 100
export const FIELD_FOCUS_TRIES = 30
/** A stage's "Required to enter" saves once picking settles, so quick picks send one change. */
export const REQUIRED_SAVE_DELAY_MS = 600

/** A card's documents, in the order its Documents tab lists them. */
export const DOC_LABELS: Record<CardDocKind, string> = {
  prd: 'PRD',
  design_brief: 'Design brief',
  notes: 'Notes',
}
export const DOC_KINDS = Object.keys(DOC_LABELS) as CardDocKind[]
/** The same names mid-sentence ("No PRD yet", "the design brief"). */
export const DOC_NAMES: Record<CardDocKind, string> = {
  prd: 'PRD',
  design_brief: 'design brief',
  notes: 'notes',
}

/** Version tags in a document's history: only AI drafts and restores stand out. */
export const DOC_SOURCE_BADGES: Partial<Record<CardDocSource, { text: string; color: string }>> = {
  agent: { text: 'AI', color: 'success' },
  revert: { text: 'Restored', color: 'warning' },
}

/**
 * The Delivery board: the BUD board, listed as a board of type Delivery for
 * engineering members. Built in, so it has no prefs row and can't be starred.
 */
export const DELIVERY_BOARD = {
  name: 'Delivery',
  key: 'BUD',
  type: 'Delivery board',
  path: '/buds',
} as const

/**
 * The sidebar's "All boards" icon: a row of boards, so it doesn't read as
 * Dashboard's tiled grid (mdi-view-dashboard-outline).
 */
export const ALL_BOARDS_ICON = 'mdi-view-carousel-outline'
