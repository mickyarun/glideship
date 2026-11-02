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

/** A card's history shows pull requests and commits that named it, linking only to https. */
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import CardActivity from '@/components/boards/card/CardActivity.vue'
import type { CardEventRead } from '@/types/boards'

const REPO = { id: 'r1', name: 'acme/web', url: 'https://github.com/acme/web' }

function repoEvent(id: string, detail: Record<string, unknown>): CardEventRead {
  return {
    id, type: 'repo_activity', board_id: 'b1', actor_id: null, actor_label: 'octo',
    from_stage_id: null, to_stage_id: null, from_category: null, to_category: null,
    detail: { repo_id: 'r1', author_login: 'octo', ...detail }, created_at: '2026-10-01T00:00:00Z',
  }
}

async function mountWith(events: CardEventRead[]) {
  const { plugins } = boardTestPlugins()
  const activity = {
    events: ref(events), next: ref(null), loading: ref(false), loadingMore: ref(false), error: ref(''),
    load: vi.fn(), more: vi.fn(), refresh: vi.fn(), reset: vi.fn(),
  }
  const wrapper = mount(CardActivity, {
    props: { activity, stages: [], nameFor: (id: string) => id, boardId: 'b1', repos: [REPO] },
    global: { plugins: plugins as never[] },
  })
  await flushPromises()
  return { wrapper, activity }
}

describe('CardActivity: repository activity', () => {
  it('shows who opened or merged a pull request, its title, ref link and repository', async () => {
    const { wrapper, activity } = await mountWith([
      repoEvent('e2', { kind: 'pr_merged', ref: '#5', url: 'https://github.com/acme/web/pull/5', title: 'Fix login' }),
      repoEvent('e1', { kind: 'commit', ref: 'a1b2c3d', url: 'https://github.com/acme/web/commit/a1b2c3d', title: 'OPS-3 tidy' }),
    ])
    expect(activity.load).toHaveBeenCalledOnce()
    const text = wrapper.text()
    expect(text).toContain('octo')
    expect(text).toContain('merged pull request')
    expect(text).toContain('Fix login')
    expect(text).toContain('pushed commit')
    expect(text).toContain('acme/web')
    const links = wrapper.findAll('a')
    expect(links.map(a => a.attributes('href'))).toEqual([
      'https://github.com/acme/web/pull/5', 'https://github.com/acme/web/commit/a1b2c3d',
    ])
    expect(links.every(a => a.attributes('rel') === 'noopener noreferrer' && a.attributes('target') === '_blank')).toBe(true)
    expect(wrapper.find('.mdi-source-merge').exists()).toBe(true)
    expect(wrapper.find('.mdi-source-commit').exists()).toBe(true)
  })

  it('never links an address that isn\'t https, and shows a title as text', async () => {
    const { wrapper } = await mountWith([
      repoEvent('e1', { kind: 'pr_opened', ref: '#9', url: 'javascript:alert(1)', title: '<b>bold</b>' }),
      repoEvent('e2', { kind: 'pr_closed', ref: '#8', url: 'http://github.com/acme/web/pull/8', title: 'Old' }),
    ])
    expect(wrapper.findAll('a')).toHaveLength(0)
    expect(wrapper.text()).toContain('#9')
    expect(wrapper.text()).toContain('<b>bold</b>')
    expect(wrapper.find('b').exists()).toBe(false)
  })
})
