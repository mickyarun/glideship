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

// The sections of a board's settings page, kept in the URL as
// ``?section=`` so a link opens the right one and the unsaved-changes
// guard can ask before a section with edits closes.

export type BoardSettingsSection = 'general' | 'stages' | 'members' | 'labels' | 'repos' | 'handover' | 'archive'

export const BOARD_SETTINGS_SECTIONS: { value: BoardSettingsSection; title: string }[] = [
  { value: 'general', title: 'General' },
  { value: 'stages', title: 'Stages' },
  { value: 'handover', title: 'Handover' },
  { value: 'members', title: 'Members and visibility' },
  { value: 'labels', title: 'Labels' },
  { value: 'repos', title: 'Repositories' },
  { value: 'archive', title: 'Archive board' },
]

/** Sections whose changes save as they're made (the others use Save). */
export const SAVES_AS_YOU_GO: ReadonlySet<BoardSettingsSection> = new Set(['stages', 'members', 'labels', 'repos', 'archive'])

/** The query key holding the open section. */
export const SECTION_QUERY_KEY = 'section'

/** The section named in the URL, or General for anything else. */
export function sectionFrom(value: unknown): BoardSettingsSection {
  const hit = BOARD_SETTINGS_SECTIONS.find(s => s.value === value)
  return hit?.value ?? 'general'
}

/** A section's path, as the section list links to it. */
export function sectionPath(boardKey: string, section: BoardSettingsSection): string {
  const base = `/boards/${encodeURIComponent(boardKey)}/settings`
  return section === 'general' ? base : `${base}?${SECTION_QUERY_KEY}=${section}`
}

/** The Import from Trello page, under a board's settings. */
export function importPath(boardKey: string): string {
  return `/boards/${encodeURIComponent(boardKey)}/settings/import`
}
