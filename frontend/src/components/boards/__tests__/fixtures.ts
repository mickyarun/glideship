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

// Builders for board tests: a card, a stage, a board detail and an axios
// error with a status, each overridable field by field.

import { AxiosError, AxiosHeaders } from 'axios'
import type { BoardAction, BoardDetail, CardSummary, StageRead } from '@/types/boards'

export function makeCard(id: string, over: Partial<CardSummary> = {}): CardSummary {
  return {
    id,
    key: `OPS-${id}`,
    number: Number(id.replace(/\D/g, '')) || 1,
    stage_id: 's1',
    position: 1,
    title: `Card ${id}`,
    priority: null,
    start_at: null,
    due_at: null,
    due_done: false,
    archived_at: null,
    updated_at: '2026-10-01T00:00:00Z',
    assignee_ids: [],
    label_ids: [],
    checklist_done: 0,
    checklist_total: 0,
    handovers: [],
    ...over,
  }
}

export function makeStage(id: string, over: Partial<StageRead> = {}): StageRead {
  return {
    id,
    name: `Stage ${id}`,
    category: 'todo',
    position: 0,
    wip_limit: null,
    is_default: false,
    open_cards: 0,
    ...over,
  }
}

export const EDITOR_CAPS: BoardAction[] = [
  'view', 'comment', 'create_card', 'edit_card', 'move_card', 'archive_card',
]
export const VIEWER_CAPS: BoardAction[] = ['view', 'comment']

export function makeDetail(over: Partial<BoardDetail> = {}): BoardDetail {
  return {
    board: {
      id: 'b1',
      key: 'OPS',
      name: 'Ops',
      description: null,
      status: 'active',
      visibility: 'org',
      handover_enabled: false,
      handover_stage_id: null,
      return_stage_id: null,
      handover_target_status: 'bud',
      ai_enabled: false,
      created_at: '2026-10-01T00:00:00Z',
      updated_at: '2026-10-01T00:00:00Z',
    },
    stages: [makeStage('s1', { is_default: true }), makeStage('s2')],
    labels: [],
    role: 'editor',
    capabilities: EDITOR_CAPS,
    starred: false,
    ...over,
  }
}

export function httpError(status: number, detail = 'Refused'): AxiosError {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError('failed', String(status), config, null, {
    status,
    statusText: '',
    headers: {},
    config,
    data: { detail },
  })
}
