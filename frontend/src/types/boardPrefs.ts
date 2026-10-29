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

// A person's saved filters and stars, the switcher's groups, a board's
// members and the server's limits. Mirrors backend/app/schemas/boards/
// prefs.py, member.py and limits.py.

import type { BUDPriority } from '@/types'
import type { BoardRole, CustomBoardItem, DeliveryBoardItem } from '@/types/boards'

/** Saved per person per board (``board_user_prefs.filters``). */
export interface SavedFilters {
  q: string | null
  assignee_ids: string[]
  label_ids: string[]
  priorities: BUDPriority[]
  archived: boolean
}

export interface PrefsRead {
  starred: boolean
  filters: SavedFilters
}

export interface SwitcherRead {
  starred: CustomBoardItem[]
  recent: CustomBoardItem[]
  other: CustomBoardItem[]
  delivery: DeliveryBoardItem | null
}

export interface MemberRead {
  user_id: string
  name: string
  avatar_url: string | null
  role: BoardRole
}

export interface MembersRead {
  members: MemberRead[]
  teams: { team_id: string; name: string; role: BoardRole }[]
}

/** Lengths and caps from ``GET /boards/limits``; never copied into the UI. */
export interface BoardLimits {
  board_name_max: number
  board_description_max: number
  stage_name_max: number
  max_stages: number
  wip_limit_max: number
  label_name_max: number
  card_title_max: number
  card_description_max: number
  doc_max: number
  comment_max: number
  checklist_text_max: number
  checklist_max_items: number
  links_max_per_card: number
  id_list_max_items: number
  search_max: number
  filters_max_bytes: number
  stage_page_size: number
  attachments: { max_file_mb: number; max_files: number; accepted_extensions: string[] }
}
