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

// A parsed Trello board and import sessions at each status, for the
// import wizard's tests.

import { AxiosError, AxiosHeaders } from 'axios'
import type { ImportSessionRead, TrelloDiscovery } from '@/types/boards'

export function makeDiscovery(over: Partial<TrelloDiscovery> = {}): TrelloDiscovery {
  return {
    source_kind: 'trello',
    board_id: 'tb1',
    board_name: 'Ops requests',
    board_url: null,
    lists: [
      { id: 'l1', name: 'Inbox', closed: false, card_count: 41, suggested_name: 'Inbox', suggested_category: 'todo', suggested_skip: false },
      { id: 'l2', name: 'Doing', closed: false, card_count: 9, suggested_name: 'Doing', suggested_category: 'in_progress', suggested_skip: false },
      { id: 'l3', name: 'Done', closed: false, card_count: 102, suggested_name: 'Done', suggested_category: 'done', suggested_skip: false },
      { id: 'l4', name: 'Old ideas', closed: true, card_count: 38, suggested_name: 'Old ideas', suggested_category: 'todo', suggested_skip: true },
    ],
    labels: [{ id: 'x1', name: 'bug', color: 'red', mapped_color: 'red' }],
    members: [
      { id: 'm1', full_name: 'Tom Okafor', username: 'tom', suggested_user_id: 'u-tom' },
      { id: 'm2', full_name: 'ops-bot', username: 'opsbot', suggested_user_id: null },
    ],
    counts: { cards: 190, archived_cards: 50, comments: 612, checklist_items: 20, attachments: 84, actions: 1000 },
    dropped: { custom_fields: 2, power_up_data: 0, covers: 0 },
    warnings: [],
    ...over,
  }
}

export function makeSession(over: Partial<ImportSessionRead> = {}): ImportSessionRead {
  return {
    id: 's1',
    source_kind: 'trello',
    mode: 'upload',
    status: 'ready',
    board_id: null,
    board_key: null,
    total_cards: 190,
    processed_count: 0,
    last_processed_index: null,
    job_id: 'job-read',
    error: null,
    discovery: makeDiscovery(),
    mapping: null,
    result: null,
    created_at: '2026-10-31T00:00:00Z',
    updated_at: '2026-10-31T00:00:00Z',
    ...over,
  }
}

/** An axios error with a status, the server's detail and response headers. */
export function apiError(status: number, detail: string, headers: Record<string, string> = {}): AxiosError {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError('failed', String(status), config, null, {
    status,
    statusText: '',
    headers,
    config,
    data: { detail },
  })
}
