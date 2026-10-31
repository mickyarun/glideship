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

// What hangs off one card: edits, its checklist, comments, attachments
// and history. Mirrors backend/app/schemas/boards/card.py (CardUpdate)
// and card_detail.py; wire fields stay snake_case.

import type { BUDPriority } from '@/types'
import type { StageCategory } from '@/types/boards/board'
import type { ImportSourceKind } from '@/types/boards/imports'

/** Card edits; omitted fields stay, ``null`` clears a nullable one. */
export interface CardUpdate {
  title?: string
  description_md?: string | null
  priority?: BUDPriority | null
  start_at?: string | null
  due_at?: string | null
  due_done?: boolean
  assignee_ids?: string[]
  label_ids?: string[]
}

export interface ChecklistItem {
  id: string
  text: string
  done: boolean
  group_name: string | null
  position: number
}

export interface CardCommentRead {
  id: string
  author_id: string | null
  /** Who wrote it when they aren't a member here (an imported comment). */
  author_label: string | null
  author_name: string | null
  author_avatar_url: string | null
  /** Where an imported comment came from; null for one written here. */
  import_source: ImportSourceKind | null
  body: string
  edited_at: string | null
  deleted_at: string | null
  created_at: string
}

export interface CardCommentPage {
  items: CardCommentRead[]
  next_cursor: string | null
}

export interface CardAttachmentRead {
  id: string
  kind: 'file' | 'link'
  filename: string
  url: string | null
  mime_type: string | null
  size_bytes: number | null
  uploaded_by: string | null
  created_at: string
}

export interface CardAttachmentLimits {
  max_file_mb: number
  max_files: number
  accepted_extensions: string[]
}

export interface CardAttachmentList {
  items: CardAttachmentRead[]
  limits: CardAttachmentLimits
}

/** BoardCardEventType in backend/app/models/board_enums.py. */
export type CardEventType =
  | 'created' | 'moved' | 'moved_board' | 'edited' | 'assigned' | 'unassigned'
  | 'commented' | 'archived' | 'restored' | 'handed_over' | 'returned' | 'delivered'
  | 'imported' | 'doc_updated' | 'ai_run'

export interface CardEventRead {
  id: string
  type: CardEventType
  board_id: string
  actor_id: string | null
  actor_label: string | null
  from_stage_id: string | null
  to_stage_id: string | null
  from_category: StageCategory | null
  to_category: StageCategory | null
  detail: Record<string, unknown>
  created_at: string
}

/** Newest first; pass ``next_before`` as ``before`` for older entries. */
export interface CardEventPage {
  items: CardEventRead[]
  next_before: string | null
}
