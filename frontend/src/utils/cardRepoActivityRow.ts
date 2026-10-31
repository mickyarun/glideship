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

// A card's ``repo_activity`` history row: a pull request opened, merged
// or closed, or a commit pushed, on a repository the board links, that
// named the card's key. The detail comes from a GitHub delivery, so every
// field is checked: the login and title show as text, the ref links to
// GitHub only through safeHref (the server builds the address from the
// repository's own name, but a page never follows anything but https),
// and an unknown kind reads as plain activity.

import type { CardEventRead } from '@/types/boards'
import { actor, section, text, type ActivityPart, type ActivityRow } from '@/utils/activity'
import { safeHref } from '@/utils/safeHref'

export type RepoActivityKind = 'pr_opened' | 'pr_merged' | 'pr_closed' | 'commit'

interface KindLook {
  icon: string
  color: string
  words: string
}

export const REPO_ACTIVITY_LOOKS: Record<RepoActivityKind, KindLook> = {
  pr_opened: { icon: 'mdi-source-pull', color: 'info', words: 'opened pull request' },
  pr_merged: { icon: 'mdi-source-merge', color: 'success', words: 'merged pull request' },
  pr_closed: { icon: 'mdi-source-branch-remove', color: 'muted', words: 'closed pull request' },
  commit: { icon: 'mdi-source-commit', color: 'primary', words: 'pushed commit' },
}

const FALLBACK_LOOK: KindLook = { icon: 'mdi-source-repository', color: 'muted', words: 'linked repository activity' }

const word = (value: unknown): string | null => (typeof value === 'string' && value.trim() ? value.trim() : null)

function lookFor(kind: unknown): KindLook {
  return typeof kind === 'string' && kind in REPO_ACTIVITY_LOOKS ? REPO_ACTIVITY_LOOKS[kind as RepoActivityKind] : FALLBACK_LOOK
}

/** The ref ("#5", "a1b2c3d") as a link when its address is https, as text otherwise. */
function refPart(ref: string | null, url: unknown): ActivityPart[] {
  if (!ref) return []
  const href = safeHref(word(url))
  return [href ? { kind: 'link', text: ref, href } : section(ref)]
}

/**
 * The row for activity on a linked repository. ``repo`` names a repository
 * by id when the board still links it (null otherwise: the row then leaves
 * it out).
 */
export function repoActivityRow(e: CardEventRead, repo: (id: string) => string | null): ActivityRow {
  const d = e.detail
  const look = lookFor(d.kind)
  const login = word(d.author_login) ?? word(e.actor_label)
  const title = word(d.title)
  const repoId = word(d.repo_id)
  const repoName = repoId ? repo(repoId) : null
  return {
    icon: look.icon,
    color: look.color,
    primary: [...actor(login), text(look.words), ...refPart(word(d.ref), d.url), ...(title ? [text(title)] : [])],
    meta: repoName ? [{ kind: 'note', text: repoName }] : undefined,
  }
}
