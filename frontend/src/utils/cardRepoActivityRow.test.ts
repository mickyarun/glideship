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

/** Pull requests and commits that named a card: icon by kind, the ref linked only when https. */
import { describe, expect, it } from 'vitest'

import type { CardEventRead } from '@/types/boards'
import { rendererFor, type ActivityPart } from '@/utils/activity'
import { cardTimelineRenderers } from '@/utils/cardTimelineRows'
import { REPO_ACTIVITY_LOOKS, repoActivityRow } from '@/utils/cardRepoActivityRow'

const REPO = '11111111-1111-1111-1111-111111111111'
const ev = (detail: Record<string, unknown>, over: Partial<CardEventRead> = {}): CardEventRead => ({
  id: 'e1', type: 'repo_activity', board_id: 'b1', actor_id: null, actor_label: 'octo',
  from_stage_id: null, to_stage_id: null, from_category: null, to_category: null,
  detail: { repo_id: REPO, kind: 'pr_opened', ref: '#5', url: 'https://github.com/acme/web/pull/5', title: 'Fix login', author_login: 'octo', ...detail },
  created_at: '2026-10-01T00:00:00Z', ...over,
})
const named = (id: string) => (id === REPO ? 'acme/web' : null)
const words = (parts: ActivityPart[]) => parts.map(p => ('text' in p ? p.text : '')).join(' ')
const link = (parts: ActivityPart[]) => parts.find(p => p.kind === 'link') as Extract<ActivityPart, { kind: 'link' }> | undefined

describe('repoActivityRow', () => {
  it('says who opened, merged or closed a pull request, with its own icon', () => {
    for (const [kind, words_] of [['pr_opened', 'opened'], ['pr_merged', 'merged'], ['pr_closed', 'closed']] as const) {
      const row = repoActivityRow(ev({ kind }), named)
      expect(words(row.primary)).toBe(`octo ${words_} pull request #5 Fix login`)
      expect(row.icon).toBe(REPO_ACTIVITY_LOOKS[kind].icon)
      expect(row.color).toBe(REPO_ACTIVITY_LOOKS[kind].color)
    }
  })

  it('reads a commit by its short sha, on the repository the board links', () => {
    const row = repoActivityRow(ev({ kind: 'commit', ref: 'a1b2c3d', url: 'https://github.com/acme/web/commit/a1b2c3d', title: 'OPS-12 tidy' }), named)
    expect(words(row.primary)).toBe('octo pushed commit a1b2c3d OPS-12 tidy')
    expect(row.icon).toBe('mdi-source-commit')
    expect(row.meta).toEqual([{ kind: 'note', text: 'acme/web' }])
  })

  it('links the ref only to an https address', () => {
    expect(link(repoActivityRow(ev({}), named).primary)?.href).toBe('https://github.com/acme/web/pull/5')
    for (const url of ['javascript:alert(1)', 'http://github.com/acme/web/pull/5', 'data:text/html,x', '/pull/5', null]) {
      const row = repoActivityRow(ev({ url }), named)
      expect(link(row.primary)).toBeUndefined()
      expect(row.primary).toContainEqual({ kind: 'section', text: '#5' })
    }
  })

  it('shows the title as text, never as a link or markup', () => {
    const row = repoActivityRow(ev({ title: '<img src=x onerror=alert(1)>' }), named)
    expect(row.primary.at(-1)).toEqual({ kind: 'text', text: '<img src=x onerror=alert(1)>' })
  })

  it('copes with a missing login, title, repository or an unknown kind', () => {
    const row = repoActivityRow(ev({ kind: 'force_push', author_login: '', title: null, repo_id: 'gone' }, { actor_label: null }), named)
    expect(words(row.primary)).toBe('linked repository activity #5')
    expect(row.meta).toBeUndefined()
    expect(repoActivityRow(ev({ author_login: null }), named).primary[0]).toEqual({ kind: 'actor', text: 'octo' })
  })

  it('is the card timeline row for repo_activity events', () => {
    const renderers = cardTimelineRenderers({ stage: () => 'x', person: () => 'x', repo: named })
    const row = rendererFor(renderers, 'repo_activity').row(ev({ kind: 'pr_merged' }))
    expect(row.icon).toBe('mdi-source-merge')
    expect(row.meta).toEqual([{ kind: 'note', text: 'acme/web' }])
  })
})
