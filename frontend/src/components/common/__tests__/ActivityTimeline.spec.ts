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

/**
 * The shared activity timeline: each event's row comes from the renderer
 * registered for its type, unknown types use the fallback, and the BUD's
 * own rows still read as before.
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

import ActivityTimeline from '@/components/common/ActivityTimeline.vue'
import BUDTimeline from '@/components/buds/BUDTimeline.vue'
import type { TimelineEvent } from '@/types'
import { plainRow, type ActivityRenderers } from '@/utils/activity'

interface Ev {
  id: string
  created_at: string
  kind: string
  who: string
}

const vuetify = createVuetify({ components, directives })

/** Each row's pieces as words: the line spaces them with a flex gap, not text. */
function rowsOf(wrapper: { element: Element }): string[] {
  return Array.from(wrapper.element.querySelectorAll('.tl-content')).map(row =>
    Array.from(row.querySelectorAll('.tl-primary > *, .tl-meta > *'))
      .map(n => n.textContent?.replace(/\s+/g, ' ').trim())
      .filter(Boolean)
      .join(' '),
  )
}
const AT = '2026-10-01T10:00:00Z'

const RENDERERS: ActivityRenderers<Ev> = {
  byType: {
    waved: { icon: 'mdi-hand-wave', color: 'primary', row: e => plainRow(e.who, 'waved') },
    moved: {
      icon: 'mdi-swap-horizontal',
      color: 'primary',
      row: e => ({
        primary: [{ kind: 'actor', text: e.who }, { kind: 'text', text: 'moved' }, { kind: 'status', text: 'Review', color: 'info' }],
        meta: [{ kind: 'badge', text: 'auto' }],
      }),
    },
  },
  fallback: { icon: 'mdi-circle-small', color: 'muted', row: e => plainRow(e.who, 'did something') },
}

// A generic component: mount() can't infer its event type, so the props
// are checked against Ev here and handed over as they are.
function mountTimeline(events: Ev[]) {
  const props = { events, loading: false, renderers: RENDERERS, typeOf: (e: Ev) => e.kind }
  return mount(ActivityTimeline, { props: props as never, global: { plugins: [vuetify] } })
}

describe('ActivityTimeline', () => {
  it('renders each event with the renderer registered for its type', () => {
    const wrapper = mountTimeline([
      { id: '1', created_at: AT, kind: 'waved', who: 'Asha' },
      { id: '2', created_at: AT, kind: 'moved', who: 'Ben' },
    ])
    const rows = rowsOf(wrapper)
    expect(rows[0]).toBe('Asha waved')
    expect(rows[1]).toContain('Ben moved Review')
    expect(rows[1]).toContain('auto')
    expect(wrapper.find('.tl-actor').text()).toBe('Asha')
  })

  it('falls back for types nobody registered, and says when there is nothing', () => {
    expect(rowsOf(mountTimeline([{ id: '1', created_at: AT, kind: 'mystery', who: 'Cy' }]))).toEqual(['Cy did something'])
    expect(mountTimeline([]).text()).toContain('No activity yet')
  })
})

describe('BUDTimeline rows', () => {
  const ev = (event_type: string, detail: Record<string, unknown> | null, actor_name: string | null = 'Dev') =>
    ({ id: event_type, event_type, actor_name, detail, created_at: AT }) as TimelineEvent

  it('keeps the BUD rows: stage moves, PR links, failures and unknown types', () => {
    const wrapper = mount(BUDTimeline, {
      props: {
        loading: false,
        events: [
          ev('status_change', { from: 'design', to: 'tech_arch' }),
          ev('pr_merged', { pr_number: 7, repo: 'web', html_url: 'https://example.test/pr/7' }),
          ev('ac_verification_failed', { passed: 1, total: 2, results: [{ implemented: false, criterion: 'Export' }] }),
          ev('ai_agent_started', null),
          ev('something_new', null),
        ],
      },
      global: { plugins: [vuetify] },
    })
    const rows = rowsOf(wrapper)
    expect(rows[0]).toBe('Dev moved Design Tech Architecture')
    expect(rows[1]).toContain('PR #7 merged on web')
    expect(wrapper.find('a[href="https://example.test/pr/7"]').exists()).toBe(true)
    expect(rows[2]).toContain('1/2 acceptance criteria verified')
    expect(rows[2]).toContain('Missing: Export')
    expect(rows[3]).toBe('Dev AI started')
    expect(rows[4]).toBe('Dev Event')
  })
})
