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

// A card's documents and their versions. Mirrors BoardCardDocKind and
// BoardCardDocState in backend/app/models/board_enums.py, BUDEditSource in
// models/bud_version.py, and backend/app/schemas/boards/doc.py.

export type CardDocKind = 'prd' | 'design_brief' | 'notes'
export type CardDocState = 'current' | 'pending_review' | 'rejected' | 'superseded'
/** Where a version came from: an edit here, MCP, an agent, an import, or a restore. */
export type CardDocSource = 'ui' | 'mcp' | 'agent' | 'migration' | 'revert'

/** One version of one document, without its text. */
export interface DocVersionRead {
  id: string
  kind: CardDocKind
  state: CardDocState
  version: number
  source: CardDocSource
  /** The stage-agent run that wrote it, and who accepted or rejected a draft. */
  agent_run_id?: string | null
  created_by: string | null
  reviewed_by?: string | null
  reviewed_at?: string | null
  created_at: string
}

export interface DocRead extends DocVersionRead {
  body_md: string
}

/** Newest first; pass ``next_before`` back as ``before`` for older versions. */
export interface DocVersionPage {
  items: DocVersionRead[]
  next_before: number | null
}

/**
 * The current version of each document a card has, and the AI drafts
 * waiting for review (newest first; none is part of the card until accepted).
 */
export interface DocList {
  items: DocRead[]
  /** Absent from a server that predates stage agents. */
  drafts?: DocRead[]
}
