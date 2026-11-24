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

// One review as the API returns it, open for the self-review; override any part.

import type { AppraisalRead } from '@/types/appraisalReview'

export function review(overrides: Partial<AppraisalRead> = {}): AppraisalRead {
  return {
    id: 'a1', user_id: 'u1', person_name: 'Priya S', manager_name: 'Ravi', cycle_name: 'Q4 2026', review_period: 'quarterly',
    period_start: '2026-10-01', period_end: '2026-12-31', self_due: '2027-01-07', manager_due: '2027-01-14',
    ack_due: '2027-01-28', status: 'self_review', drafting_mode: 'manual', summary_status: 'none', summary: [],
    summary_hidden: false, period_facts: [],
    timeline: [{
      check_in_id: 'c1', period_start: '2026-10-01', status: 'employee_added', sent: true, note: { lines: {}, blocking: '', next_month: '' },
      facts: [{ source: 'board_cards', id: 'f1', key: 'OPS-1', title: 'Close', url: '/b', verb: 'done', done_at: null, private: false }],
      links: [{ id: 'l1', url: 'https://doc.test', title: 'Spec', heading: 'team', goal_id: null }],
    }],
    goals: [{ id: 'g1', position: 1, title: 'Ship refunds', measure: '', added_mid_period: false, accepted_at: null, self_result: null, self_reason: null, self_evidence: [], result: null, draft_result: null, manager_reason: null }],
    self_score: { band: null, reason: '', evidence: [], submitted_at: null },
    manager_score: null, manager_only: null, send_back_note: null, reply: null, shared_at: null, acknowledged_at: null,
    growth: { open: false, can_edit: false, is_self: true, strength: '', focus: '', next_period_start: '2027-01-01', limit: 3, goals: [] },
    can: { edit_self: true, edit_manager: false, send_back: false, share: false, acknowledge: false },
    ...overrides,
  }
}
