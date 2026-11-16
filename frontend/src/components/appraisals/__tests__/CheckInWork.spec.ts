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

/** The check-in's "Your work in Glideship" list and its headings. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CheckInHeadings from '@/components/appraisals/CheckInHeadings.vue'
import CheckInWork from '@/components/appraisals/CheckInWork.vue'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import type { FactView } from '@/types/appraisal'

function fact(overrides: Partial<FactView> = {}): FactView {
  return {
    source: 'board_cards', id: 'f1', key: 'OPS-212', title: 'January month-end close',
    url: '/boards/OPS/cards/212', verb: 'done', done_at: '2026-10-15T09:00:00Z', private: false,
    ...overrides,
  }
}

function mountWork(facts: FactView[], editable = true) {
  const { plugins } = boardTestPlugins()
  return mount(CheckInWork, {
    global: { plugins: plugins as never[] },
    props: { facts, tags: {}, goals: [], editable, monthLabel: 'October 2026' },
  })
}

describe('CheckInWork', () => {
  it('shows a chip per fact, grouped under its source', () => {
    const wrapper = mountWork([fact(), fact({ id: 'f2', key: 'PR #812', source: 'pull_requests', title: 'Retries' })])
    expect(wrapper.findAll('.work__key').map(k => k.text())).toEqual(['OPS-212', 'PR #812'])
    expect(wrapper.findAll('.work__source').map(s => s.text())).toEqual(['Board cards · 1', 'Pull requests · 1'])
  })

  it('shows a private fact without its title or link', () => {
    const wrapper = mountWork([fact({ private: true, key: 'private record · Board', title: null, url: null })], false)
    expect(wrapper.find('a.work__key').exists()).toBe(false)
    expect(wrapper.text()).toContain("Can't be opened by you; it still counts.")
  })

  it('says so when Glideship recorded nothing', () => {
    expect(mountWork([]).text()).toContain('Glideship has nothing recorded for this month.')
  })

  it('offers the goal picker only to the person writing', () => {
    expect(mountWork([fact()], true).find('.work__tag').exists()).toBe(true)
    expect(mountWork([fact()], false).find('.work__tag').exists()).toBe(false)
  })
})

describe('CheckInHeadings', () => {
  function mountHeadings(editable: boolean) {
    const { plugins } = boardTestPlugins()
    return mount(CheckInHeadings, {
      global: { plugins: plugins as never[] },
      props: { lines: { team: ['Covered support'] }, links: [], meanings: {}, editable },
    })
  }

  it('offers "Add a line" and "Add a link" right under every heading', () => {
    const wrapper = mountHeadings(true)
    expect(wrapper.findAll('.heading__actions')).toHaveLength(4)
    expect(wrapper.findAll('.heading__empty')).toHaveLength(3)
  })

  it('adds an empty line to that heading', async () => {
    const wrapper = mountHeadings(true)
    await wrapper.findAll('.heading__actions')[0].find('button').trigger('click')
    expect(wrapper.emitted('update:lines')?.[0]).toEqual([{ team: ['Covered support'], delivery_quality: [''] }])
  })

  it('shows lines read-only to anyone else', () => {
    const wrapper = mountHeadings(false)
    expect(wrapper.find('.heading__actions').exists()).toBe(false)
    expect(wrapper.text()).toContain('Covered support')
  })
})
