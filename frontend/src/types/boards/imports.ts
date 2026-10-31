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

// Board import sessions as the API returns them. Mirrors
// backend/app/schemas/boards/imports.py, import_mapping.py and
// trello_discovery.py. The mapping vocabulary is the source's neutral
// one: a *group* is a Trello list, a *member* a Trello person.

import type { BoardVisibility, LabelColor, StageCategory } from '@/types/boards/board'

export type ImportSourceKind = 'trello'
export type ImportMode = 'upload' | 'api'
export type ImportStatus = 'pending' | 'parsing' | 'ready' | 'running' | 'completed' | 'failed'
export type TrelloWarning = 'action_cap'

/** A queued job (202): its progress comes on the job socket. */
export interface ImportAccepted {
  jobId: string
  sessionId: string
}

export interface DiscoveredList {
  id: string
  name: string
  closed: boolean
  card_count: number
  suggested_name: string
  suggested_category: StageCategory
  suggested_skip: boolean
}

export interface DiscoveredLabel {
  id: string
  name: string
  color: string | null
  mapped_color: LabelColor
}

export interface DiscoveredMember {
  id: string
  full_name: string
  username: string
  suggested_user_id: string | null
}

export interface DiscoveryCounts {
  cards: number
  archived_cards: number
  comments: number
  checklist_items: number
  attachments: number
  actions: number
}

export interface DroppedCounts {
  custom_fields: number
  power_up_data: number
  covers: number
}

export interface TrelloDiscovery {
  source_kind: 'trello'
  board_id: string
  board_name: string
  board_url: string | null
  lists: DiscoveredList[]
  labels: DiscoveredLabel[]
  members: DiscoveredMember[]
  counts: DiscoveryCounts
  dropped: DroppedCounts
  warnings: TrelloWarning[]
}

export type StageChoice = 'new' | 'existing' | 'skip'
export type ArchivedChoice = 'skip' | 'archive'

export interface NewBoardTarget {
  kind: 'new'
  name: string
  key: string
  visibility: BoardVisibility
  description?: string | null
}

export interface ExistingBoardTarget {
  kind: 'existing'
  key: string
}

export type ImportTarget = NewBoardTarget | ExistingBoardTarget

export interface GroupMapping {
  group_id: string
  action: StageChoice
  name?: string | null
  category?: StageCategory | null
  stage_id?: string | null
}

export interface MemberMapping {
  member_id: string
  user_id: string | null
}

export interface ImportMapping {
  target: ImportTarget
  groups: GroupMapping[]
  members: MemberMapping[]
  archived_cards: ArchivedChoice
}

export interface ImportResult {
  imported: number
  skipped: number
  failed: number
  already_imported: number
  dropped: Record<string, number>
  attachment_bytes: number
  suppressed_events: number
}

export interface ImportSessionRead {
  id: string
  source_kind: ImportSourceKind
  mode: ImportMode
  status: ImportStatus
  board_id: string | null
  board_key: string | null
  total_cards: number | null
  processed_count: number
  last_processed_index: number | null
  job_id: string | null
  error: string | null
  discovery: TrelloDiscovery | null
  mapping: ImportMapping | null
  result: ImportResult | null
  created_at: string
  updated_at: string
}

/** One of the connected Trello member's open boards. */
export interface TrelloBoardOption {
  id: string
  name: string
  url: string | null
}

/** Whether Trello is connected; never the key or token. */
export interface TrelloSettingsRead {
  configured: boolean
  member_username: string | null
  connected_at: string | null
}

export interface TrelloCredentialsWrite {
  api_key: string
  token: string
}
