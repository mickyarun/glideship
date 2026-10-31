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

// Handing a card over to Delivery, sending a BUD back, and a BUD's Origin
// panel. Mirrors backend/app/schemas/boards/handover.py and
// handover_return.py. A BUD's title is only sent to someone who may open
// the BUD (``can_open_bud``); everyone else sees its key and status.

import type { BUDPriority, BUDStatus } from '@/types'
import type { CardCommentPage } from '@/types/boards/cardDetail'
import type { CardDetail } from '@/types/boards/card'
import type { HandoverTarget } from '@/types/boards/settings'

export type HandoverMode = 'create' | 'link'
export type HandoverStatus = 'active' | 'returned'

export type HandoverWarningCode = 'SIMILAR_BUDS' | 'ALREADY_HANDED_OVER' | 'NO_REQUIREMENTS' | 'CHECKLIST_OPEN'

/** The codes a handover, send-back or origin refusal sends beside ``detail``. */
export type HandoverErrorCode =
  | 'HANDOVER_DISABLED'
  | 'HANDOVER_NEEDS_PERMISSION'
  | 'HANDOVER_NEEDS_REQUIREMENTS'
  | 'BUD_HAS_OTHER_ORIGIN'
  | 'BUD_ALREADY_LINKED'
  | 'BUD_NOT_OPEN'
  | 'HANDOVER_NOT_ACTIVE'
  | 'BUD_PAST_RETURN'
  | 'BUD_NOT_RETURNED'
  | 'HANDOVER_STAGE_STARTED'

export interface HandoverRequest {
  mode: HandoverMode
  /** Left out: the board's default landing. */
  target_status?: HandoverTarget
  /** Link mode only. */
  bud_id?: string
}

/** Edits made in the dialog; anything left out keeps the preview's value. */
export interface HandoverOverrides {
  title?: string
  requirements_md?: string
  impacted_repo_ids?: string[]
}

export interface HandoverConfirm extends HandoverRequest {
  /** One per dialog opening, so a retry or a double click returns the first result. */
  idempotency_key: string
  overrides?: HandoverOverrides
  confirm_open_checklist?: boolean
  auto_generate_phases?: Record<string, boolean>
  stage_skill_overrides?: Record<string, string>
}

export interface ImpactedRepo {
  repo_id: string
  repo_name: string
}

export interface SimilarBUD {
  bud_id: string
  key: string
  title: string
  status: BUDStatus
  /** Lower is closer. */
  distance: number
}

export interface HandoverWarning {
  code: HandoverWarningCode
  message: string
}

/** A discarded BUD a create would bring back with its number. */
export interface HandoverReopens {
  bud_key: string
  status: BUDStatus
}

export interface HandoverPreview {
  mode: HandoverMode
  target_status: HandoverTarget
  title: string
  requirements_md: string
  figma_url: string | null
  priority: BUDPriority
  impacted_repos: ImpactedRepo[]
  similar: SimilarBUD[]
  warnings: HandoverWarning[]
  reopens?: HandoverReopens | null
}

export interface HandoverRead {
  id: string
  card_id: string
  status: HandoverStatus
  linked_existing: boolean
  target_status: HandoverTarget | null
  bud_id: string | null
  bud_key: string | null
  /** Only for someone who may open the BUD. */
  bud_title?: string | null
  bud_status: BUDStatus | null
  /** ``buds:view`` with engineering access. */
  can_open_bud?: boolean
  handed_over_by: string | null
  handed_over_at: string
  returned_at: string | null
  return_reason: string | null
  /** The target stage's agents didn't start; a retry starts them. */
  stage_start_failed?: boolean
}

export interface HandoverResult {
  handover: HandoverRead
  card: CardDetail
  /** The BUD entered design with generation on and no designs yet: start them as the BUD page does. */
  design_available?: boolean
}

export interface HandoverList {
  items: HandoverRead[]
  can_hand_over: boolean
}

export interface OriginCard {
  key: string
  number: number
  title: string
  board: { key: string; name: string }
}

/**
 * Where a BUD came from. ``card`` is null when it wasn't handed over
 * (``hidden`` false) or its board is one I can't open (``hidden`` true).
 */
export interface BUDOrigin {
  card: OriginCard | null
  hidden: boolean
  /** The card's comments, newest first. */
  comments: CardCommentPage | null
  handovers: HandoverRead[]
}
