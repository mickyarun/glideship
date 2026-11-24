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

/** The one Appraisals page: which tabs show, and which tab a page sits under. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import AppraisalTabs from '@/components/appraisals/AppraisalTabs.vue'
import { peopleRoutes } from '@/router/routes/people'
import type { TodoItem } from '@/types/appraisalTodo'
import { appraisalTabs, tabForRoute } from '@/utils/appraisalTabs'
import { todoCounts, todoRoute } from '@/utils/appraisalTodo'
import { appraisalPlugins } from './mountAppraisal'

describe('appraisal tabs', () => {
  it('shows the team to managers and cycles to HR, your own to everyone', () => {
    const keys = (hasReports: boolean, canManage: boolean) => appraisalTabs({ hasReports, canManage }).map(t => t.label)
    expect(keys(false, false)).toEqual(['Your own'])
    expect(keys(true, false)).toEqual(['Your team', 'Your own'])
    expect(keys(true, true)).toEqual(['Your team', 'Your own', 'Cycles'])
  })

  it('puts list pages under a tab and pages opened by id under none', () => {
    expect(tabForRoute('appraisal-my-review')).toBe('own')
    expect(tabForRoute('appraisal-cycle')).toBe('cycles')
    expect(tabForRoute('appraisal-team')).toBe('team')
    expect(tabForRoute('appraisal-review')).toBeNull()
    expect(tabForRoute(null)).toBeNull()
    expect(tabForRoute('appraisal-review', true)).toBe('own')
  })

  it('links each tab to its old route and marks the current one', async () => {
    const { plugins } = await appraisalPlugins('/appraisals/cycles/c1')
    const wrapper = mount(AppraisalTabs, { global: { plugins: plugins as never[] }, props: { hasReports: true, canManage: true } })
    const links = wrapper.findAll('a')
    expect(links.map(a => a.attributes('href'))).toEqual(['/appraisals/team', '/appraisals', '/appraisals/cycles'])
    expect(links.map(a => a.attributes('aria-current'))).toEqual([undefined, undefined, 'page'])
  })

  it('shows no strip when there is only one tab', async () => {
    const { plugins } = await appraisalPlugins('/appraisals')
    const wrapper = mount(AppraisalTabs, { global: { plugins: plugins as never[] }, props: { hasReports: false, canManage: false } })
    expect(wrapper.find('nav').exists()).toBe(false)
  })

  it('keeps every appraisal route at its old path under the one page', () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', children: peopleRoutes }] })
    expect(router.resolve({ name: 'appraisal-home' }).path).toBe('/appraisals')
    expect(router.resolve({ name: 'appraisal-review', params: { id: 'a1' } }).path).toBe('/appraisals/reviews/a1')
    expect(router.resolve('/appraisals/cycles/c1').name).toBe('appraisal-cycle')
    expect(router.resolve('/appraisals/review').matched).toHaveLength(3)
  })

  it('counts what is to do on each tab', async () => {
    const item = (role: TodoItem['role'], target: TodoItem['target']): TodoItem => ({
      kind: 'note', role, person_name: 'Priya', cycle_name: null, due_on: null, late: false, target, target_id: 'x1', count: null,
    })
    const waiting = { ...item('team', 'feedback'), kind: 'waiting_on_check_in' as const }
    const items = [item('team', 'feedback'), item('team', 'goals'), item('own', 'check_in'), waiting]
    expect(todoCounts(items)).toEqual({ own: 1, team: 2, cycles: 0 })
    expect(todoRoute(items[0])).toEqual({ name: 'appraisal-notes', params: { id: 'x1' } })
    expect(todoRoute(item('cycles', 'cycle'))).toEqual({ name: 'appraisal-cycle', params: { id: 'x1' } })
    const { plugins } = await appraisalPlugins('/appraisals')
    const wrapper = mount(AppraisalTabs, {
      global: { plugins: plugins as never[] },
      props: { hasReports: true, canManage: true, counts: todoCounts(items) },
    })
    expect(wrapper.findAll('a').map(a => a.text())).toEqual(['Your team 2', 'Your own 1', 'Cycles'])
    expect(wrapper.find('[aria-label="2 to do"]').exists()).toBe(true)
  })
})
