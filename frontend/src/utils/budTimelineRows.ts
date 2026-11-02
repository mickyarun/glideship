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

// A BUD's timeline rows, registered by event type for ActivityTimeline.
// Types with nothing more to say than their label (and unknown types)
// read "{actor} {label}".

import type { TimelineEvent } from '@/types'
import { actor, plainRow, section, text, type ActivityPart, type ActivityRenderers, type ActivityRow } from '@/utils/activity'
import { HANDOVER_ROWS } from '@/utils/budHandoverTimelineRows'
import {
  DEFAULT_CONFIG, EVENT_MAP, continuityTooltip, formatAgent, formatFeatureTitles, formatRole, formatSection,
  formatShortDate, formatSingleFeatureTitle, statusColor, statusLabel, type Detail,
} from '@/utils/budTimelineFormat'

const str = (value: unknown): string => (value == null ? '' : String(value))
const slack = (label: string): ActivityPart => ({ kind: 'badge', text: label, color: 'brand', icon: 'mdi-slack' })
const status = (value: unknown): ActivityPart => ({ kind: 'status', text: statusLabel(str(value)), color: statusColor(str(value)) })
const agent = (d: Detail): ActivityPart => ({ kind: 'badge', text: formatAgent(String(d?.agent ?? 'agent')), color: 'brand' })
const reason = (d: Detail): ActivityPart[] => (d?.reason ? [text(`Reason: ${str(d.reason)}`)] : [])

function assignMethod(d: Detail): ActivityPart[] {
  if (d?.method === 'auto_round_robin') return [{ kind: 'badge', text: 'auto', color: 'primary', icon: 'mdi-autorenew' }]
  if (d?.method === 'manual') return [{ kind: 'badge', text: 'manual' }]
  if (d?.method === 'continuity') {
    return [{ kind: 'badge', text: 'continuity', color: 'primary', icon: 'mdi-restart', title: continuityTooltip(d) }]
  }
  return []
}

function missingCriteria(d: Detail): string[] {
  const results = Array.isArray(d?.results) ? (d.results as Array<Record<string, unknown>>) : []
  return results.filter(r => !r.implemented).map(r => `Missing: ${str(r.criterion)}`)
}

type Row = (event: TimelineEvent, d: Detail) => ActivityRow

const ROWS: Record<string, Row> = {
  created: (e, d) => ({
    primary: [...actor(e.actor_name), text('created this BUD')],
    meta: d?.source === 'slack_triage' ? [slack('Slack triage')] : [],
  }),
  requested: (_e, d) => ({
    primary: [text('Requested by'), ...actor(String(d?.requester_name ?? 'unknown'))],
    meta: [slack(String(d?.channel ?? 'Slack'))],
  }),
  approved: (e, d) => ({
    primary: [...actor(String(d?.approver_name ?? e.actor_name ?? 'Unknown')), text('approved this feature')],
  }),
  status_change: (e, d) => ({
    primary: [...actor(e.actor_name), text('moved'), status(d?.from), { kind: 'arrow' }, status(d?.to)],
  }),
  assigned: (_e, d) => ({
    primary: [text('Assigned to'), ...actor(String(d?.assignee_name ?? 'unknown'))],
    meta: [
      ...(d?.role ? [{ kind: 'badge', text: formatRole(String(d.role)), variant: 'outlined' } as ActivityPart] : []),
      ...assignMethod(d),
    ],
  }),
  unassigned: e => plainRow(e.actor_name, 'removed assignment'),
  ai_agent_completed: (_e, d) => ({
    primary: [
      { kind: 'icon', icon: 'mdi-check-circle', color: 'success' }, text('AI'), agent(d), text('completed on'),
      section(formatSection(String(d?.section ?? ''))),
    ],
  }),
  ai_agent_failed: (_e, d) => ({
    primary: [
      { kind: 'icon', icon: 'mdi-alert-circle', color: 'error' }, text('AI'), agent(d), text('failed', 'error'),
      text('on'), section(formatSection(String(d?.section ?? ''))),
    ],
  }),
  design_generated: (_e, d) => ({
    primary: [text('Design wireframe generated')],
    meta: d?.repo_id ? [{ kind: 'badge', text: 'repo', color: 'primary', icon: 'mdi-source-repository' }] : [],
  }),
  feature_linked: (e, d) => ({ primary: [...actor(e.actor_name), text('linked'), section(formatFeatureTitles(d))] }),
  feature_unlinked: (e, d) => ({
    primary: [...actor(e.actor_name), text('unlinked'), section(formatSingleFeatureTitle(d))],
  }),
  features_auto_linked: (_e, d) => ({
    primary: [...actor('PM Agent'), text('auto-linked'), section(formatFeatureTitles(d))],
  }),
  content_updated: (e, d) => ({
    primary: [...actor(e.actor_name), text('updated'), section(formatSection(String(d?.section ?? '')))],
  }),
  all_prs_merged: () => ({ primary: [text('All PRs merged — ready for testing')] }),
  estimate_generated: (_e, d) => ({
    primary: [
      text(`AI estimated PROD by ${formatShortDate(d?.prod_p70 as string | null | undefined)}`),
      { kind: 'note', text: `(${str(d?.trigger)})` },
    ],
    meta: d?.complexity ? [text(`Complexity: ${str(d.complexity)}/5`)] : [],
  }),
  estimate_overridden: (e, d) => ({
    primary: [
      ...actor(e.actor_name),
      text(`overrode ${str(d?.phase)} deadline to ${formatShortDate(d?.new_date as string | null | undefined)}`),
    ],
    meta: reason(d),
  }),
  ac_verification_passed: (_e, d) => ({ primary: [text(`All ${str(d?.total)} acceptance criteria verified`)] }),
  ac_verification_failed: (_e, d) => ({
    tone: 'error',
    primary: [text(`${str(d?.passed)}/${str(d?.total)} acceptance criteria verified`)],
    lines: missingCriteria(d),
  }),
  status_override: (e, d) => ({
    primary: [...actor(e.actor_name), text(`manually advanced to ${str(d?.to)}`)],
    meta: reason(d),
  }),
  code_review_rerun: (e, d) => ({
    primary: [...actor(e.actor_name), text(`re-ran code review (${d?.start_fresh ? 'fresh session' : 'resumed'})`)],
    meta: (d?.cleared_comment_count as number) > 0 ? [text(`Cleared ${str(d?.cleared_comment_count)} prior finding(s)`)] : [],
  }),
}

function prRow(e: TimelineEvent, d: Detail): ActivityRow {
  return {
    primary: [
      text(`PR #${str(d?.pr_number)}`),
      text(`${e.event_type === 'pr_opened' ? 'opened' : 'merged'} on`),
      section(str(d?.repo)),
    ],
    meta: d?.html_url ? [{ kind: 'link', text: 'View on GitHub', href: String(d.html_url) }] : [],
  }
}
ROWS.pr_opened = prRow
ROWS.pr_merged = prRow
Object.assign(ROWS, HANDOVER_ROWS)

export const BUD_TIMELINE_RENDERERS: ActivityRenderers<TimelineEvent> = {
  byType: Object.fromEntries(
    Object.entries(EVENT_MAP).map(([type, cfg]) => {
      const row = ROWS[type]
      return [type, {
        icon: cfg.icon,
        color: cfg.color,
        row: (e: TimelineEvent) => (row ? row(e, e.detail) : plainRow(e.actor_name, cfg.label)),
      }]
    }),
  ),
  fallback: { ...DEFAULT_CONFIG, row: e => plainRow(e.actor_name, DEFAULT_CONFIG.label) },
}
