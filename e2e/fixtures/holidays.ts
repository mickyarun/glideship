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

/** Holiday calendars set up through the real admin API, as HR would. */
import type { Api } from './api.ts'

export interface HolidaySeed {
  /** `YYYY-MM-DD` */
  date: string
  name: string
  kind?: 'mandatory' | 'optional'
}

interface Policy {
  id: string
  name: string
}

/** The id of the policy `api`'s member follows. */
export async function ownPolicyId(api: Api): Promise<string> {
  const summary = await api.get<{ policy: Policy }>('leave/me/summary')
  return summary.policy.id
}

/** A second office's policy, with a working week and no leave types. */
export function addPolicy(api: Api, name: string): Promise<Policy> {
  return api.post<Policy>('leave/policies', { name })
}

export async function addHolidays(api: Api, policyId: string, holidays: HolidaySeed[]): Promise<void> {
  for (const holiday of holidays) {
    await api.post(`leave/policies/${policyId}/holidays`, { kind: 'mandatory', ...holiday })
  }
}
