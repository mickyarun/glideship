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

// Names and words for a BUD's timeline rows (utils/budTimelineRows.ts):
// each event type's dot, roles, sections, agents and feature titles.

import { BUD_STATUS_COLORS, BUD_STATUS_LABELS, type BUDStatus } from '@/types'

export interface EventConfig {
  icon: string
  color: string
  label: string
}

export const EVENT_MAP: Record<string, EventConfig> = {
  created: { icon: 'mdi-plus-circle', color: 'success', label: 'BUD created' },
  requested: { icon: 'mdi-message-text', color: 'info', label: 'Requested' },
  approved: { icon: 'mdi-check-decagram', color: 'success', label: 'Approved' },
  status_change: { icon: 'mdi-swap-horizontal', color: 'primary', label: 'Status changed' },
  assigned: { icon: 'mdi-account-check', color: 'primary', label: 'Assigned' },
  unassigned: { icon: 'mdi-account-remove', color: 'muted', label: 'Unassigned' },
  ai_agent_started: { icon: 'mdi-robot', color: 'info', label: 'AI started' },
  ai_agent_completed: { icon: 'mdi-robot', color: 'success', label: 'AI completed' },
  ai_agent_failed: { icon: 'mdi-robot-off', color: 'error', label: 'AI failed' },
  content_updated: { icon: 'mdi-pencil', color: 'primary', label: 'Content updated' },
  design_generated: { icon: 'mdi-palette', color: 'primary', label: 'Design generated' },
  comment: { icon: 'mdi-comment-text', color: 'muted', label: 'Comment' },
  pr_opened: { icon: 'mdi-source-pull', color: 'info', label: 'PR opened' },
  pr_merged: { icon: 'mdi-source-merge', color: 'success', label: 'PR merged' },
  all_prs_merged: { icon: 'mdi-check-all', color: 'success', label: 'All PRs merged' },
  estimate_generated: { icon: 'mdi-chart-timeline-variant', color: 'info', label: 'Estimate updated' },
  estimate_overridden: { icon: 'mdi-calendar-edit', color: 'warning', label: 'Estimate overridden' },
  ac_verification_passed: { icon: 'mdi-check-decagram', color: 'success', label: 'ACs verified' },
  ac_verification_failed: { icon: 'mdi-alert-circle', color: 'error', label: 'ACs incomplete' },
  status_override: { icon: 'mdi-shield-alert', color: 'warning', label: 'Manual override' },
  code_review_rerun: { icon: 'mdi-refresh', color: 'info', label: 'Code review re-run' },
  feature_linked: { icon: 'mdi-link-plus', color: 'primary', label: 'Feature linked' },
  feature_unlinked: { icon: 'mdi-link-off', color: 'muted', label: 'Feature unlinked' },
  features_auto_linked: { icon: 'mdi-robot', color: 'primary', label: 'Features auto-linked' },
}

export const DEFAULT_CONFIG: EventConfig = { icon: 'mdi-circle-small', color: 'muted', label: 'Event' }

const ROLE_LABELS: Record<string, string> = {
  pm: 'Product Manager',
  designer: 'Designer',
  developer: 'Developer',
  qa: 'QA Engineer',
  tech_lead: 'Tech Lead',
  admin: 'Admin',
  org_owner: 'Owner',
}

const SECTION_LABELS: Record<string, string> = {
  requirements_md: 'Requirements',
  tech_spec_md: 'Tech Spec',
  test_plan_md: 'Test Plan',
  design: 'Design',
  title: 'Title',
}

const AGENT_LABELS: Record<string, string> = {
  'product-manager': 'PM Agent',
  'designer': 'Design Agent',
  'qa-engineer': 'QA Agent',
  'tech-planner': 'Tech Planner',
  'test-planner': 'Test Planner',
}

export type Detail = Record<string, unknown> | null | undefined

export function statusColor(s: string): string {
  return BUD_STATUS_COLORS[s as BUDStatus] ?? 'muted'
}

export function statusLabel(s: string): string {
  return BUD_STATUS_LABELS[s as BUDStatus] ?? s.toUpperCase()
}

export function formatRole(role: string): string {
  return ROLE_LABELS[role] ?? role
}

export function continuityTooltip(detail: Detail): string {
  if (!detail) return 'Carried over from a previous phase'
  const from = detail.continuity_from_role
  if (typeof from === 'string' && from) {
    return `Carried over from previous ${formatRole(from)}`
  }
  return 'Carried over from a previous phase'
}

export function formatSection(section: string): string {
  return SECTION_LABELS[section] ?? section
}

export function formatAgent(agent: string): string {
  return AGENT_LABELS[agent] ?? agent
}

// Render the titles list on feature_linked / features_auto_linked events.
// Trims empties (backend writes "" when a title can't be resolved), shows the
// first two by name, and falls back to a "N features" count when the detail
// is missing entirely (older events written before titles were captured).
const MAX_TITLES_INLINE = 2
export function formatFeatureTitles(detail: Detail): string {
  const titles = Array.isArray(detail?.feature_titles)
    ? (detail.feature_titles as unknown[]).map(String).filter(t => t.length > 0)
    : []
  const count = Number(detail?.count ?? titles.length)
  if (titles.length === 0) {
    return count === 1 ? '1 feature' : `${count} features`
  }
  if (titles.length <= MAX_TITLES_INLINE) {
    return titles.join(', ')
  }
  const head = titles.slice(0, MAX_TITLES_INLINE).join(', ')
  const rest = titles.length - MAX_TITLES_INLINE
  return `${head} and ${rest} more`
}

export function formatSingleFeatureTitle(detail: Detail): string {
  const title = typeof detail?.feature_title === 'string' ? detail.feature_title : ''
  return title.length > 0 ? title : 'a feature'
}

export function formatShortDate(dateStr: string | undefined | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
