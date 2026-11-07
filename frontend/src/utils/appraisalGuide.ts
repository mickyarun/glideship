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

/** The guide's "at a glance" lines, worded from the cycle or the org's settings (pure). */

import type { GuideRead } from '@/types/appraisalSetup'
import { longDate } from '@/utils/appraisalSetup'

const REVIEW: Record<GuideRead['review_period'], string> = {
  quarterly: 'a review every quarter',
  half_yearly: 'a review every half year',
  yearly: 'a review once a year',
}
const FEEDBACK: Record<GuideRead['feedback_cadence'], string> = {
  monthly: 'monthly feedback from your manager',
  quarterly: 'quarterly feedback from your manager',
  in_review: 'your manager’s feedback as part of each quarterly review',
}

/** "Monthly check-ins, monthly feedback from your manager, a review every quarter, …" */
export function guideGlance(guide: GuideRead): string {
  const checkIns = guide.checkin_cadence === 'monthly' ? 'Monthly check-ins' : 'Quarterly check-ins'
  const ai = guide.ai_drafting ? ' AI drafts each check-in from your work; you can change anything.' : ''
  return `${checkIns}, ${FEEDBACK[guide.feedback_cadence]}, ${REVIEW[guide.review_period]}, then a growth conversation.${ai}`
}

/** The running cycle's dates, or "" when no cycle is running. */
export function guideDates(guide: GuideRead): string {
  if (!guide.cycle_name || !guide.self_due || !guide.manager_due) return ''
  return `${guide.cycle_name}: self-review due ${longDate(guide.self_due)}, manager review due ${longDate(guide.manager_due)}.`
}
