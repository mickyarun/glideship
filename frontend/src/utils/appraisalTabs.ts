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

/** The tabs on the one Appraisals page: who sees each, and which pages sit under it (pure). */

export type AppraisalTabKey = 'team' | 'own' | 'cycles'

export interface AppraisalTab {
  key: AppraisalTabKey
  label: string
  /** The route the tab opens. */
  route: string
}

const TABS: AppraisalTab[] = [
  { key: 'team', label: 'Your team', route: 'appraisal-team' },
  { key: 'own', label: 'Your own', route: 'appraisal-my-month' },
  { key: 'cycles', label: 'Cycles', route: 'appraisal-cycles' },
]

/**
 * Pages that belong to one tab. A page opened by id (a check-in, goals, a
 * review, notes) can be anyone's, so it sits under no tab.
 */
const PAGES: Record<AppraisalTabKey, string[]> = {
  team: ['appraisal-team'],
  own: ['appraisal-my-month', 'appraisal-my-review'],
  cycles: ['appraisal-cycles', 'appraisal-cycle', 'appraisal-settings', 'appraisal-role-templates'],
}

/** The tabs this person sees: their team only with reports, cycles only with manage. */
export function appraisalTabs(access: { hasReports: boolean; canManage: boolean }): AppraisalTab[] {
  return TABS.filter(t => (t.key === 'team' ? access.hasReports : t.key === 'cycles' ? access.canManage : true))
}

/** The tab a route sits under, or null for a page opened by id. */
export function tabForRoute(name: string | null | undefined): AppraisalTabKey | null {
  const hit = (Object.keys(PAGES) as AppraisalTabKey[]).find(k => PAGES[k].includes(String(name)))
  return hit ?? null
}
