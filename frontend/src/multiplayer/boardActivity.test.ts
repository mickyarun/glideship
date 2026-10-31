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

/** The org room's board_activity message, checked again on the client. */
import { describe, expect, it } from 'vitest'
import { parseBoardActivity } from './boardActivity'

const ACTOR = '22222222-2222-2222-2222-222222222222'

describe('parseBoardActivity', () => {
  it('keeps a known kind, its actor and well-formed keys', () => {
    expect(parseBoardActivity({ kind: 'card_done', actor_id: ACTOR, board_key: 'OPS', card_key: 'OPS-12' })).toEqual({
      kind: 'card_done', actor_id: ACTOR, board_key: 'OPS', card_key: 'OPS-12',
    })
    expect(parseBoardActivity({ kind: 'bud_delivered', actor_id: null })).toEqual({ kind: 'bud_delivered', actor_id: null })
  })

  it('drops anything with an unknown kind or a malformed actor', () => {
    for (const raw of [null, 'x', { kind: 'card_moved', actor_id: ACTOR }, { kind: 'handover', actor_id: 'me' }, { kind: 'handover', actor_id: 7 }]) {
      expect(parseBoardActivity(raw)).toBeNull()
    }
  })

  it('drops keys that are not keys, a card key without a board key, and any title', () => {
    expect(parseBoardActivity({ kind: 'handover', actor_id: ACTOR, board_key: 'ops<b>', card_key: 'OPS-1', title: 'Secret' })).toEqual({
      kind: 'handover', actor_id: ACTOR,
    })
    expect(parseBoardActivity({ kind: 'handover', actor_id: ACTOR, board_key: 'OPS', card_key: 'OPS-x' })).toEqual({
      kind: 'handover', actor_id: ACTOR, board_key: 'OPS',
    })
  })
})
