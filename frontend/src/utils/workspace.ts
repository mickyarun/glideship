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

/**
 * Which workspace a user can open, and where they land after sign-in.
 *
 * Mirrors the backend's `workspace:engineering` gate: roles without it
 * (sales, HR) only see the people workspace, so sending them to the
 * engineering dashboard would bounce off a 403.
 */
import type { RouteLocationRaw } from 'vue-router'

export const WORKSPACE_ENGINEERING = 'workspace:engineering'

export type Workspace = 'engineering'

const WORKSPACE_PERMISSION: Record<Workspace, string> = {
  engineering: WORKSPACE_ENGINEERING,
}

export function canOpenWorkspace(
  permissions: readonly string[] | null | undefined,
  workspace: Workspace,
): boolean {
  return permissions?.includes(WORKSPACE_PERMISSION[workspace]) ?? false
}

export const BOARDS_VIEW = 'boards:view'

/**
 * Landing route for a signed-in user, based on what they can open:
 * engineers get the dashboard, anyone else who can open a team board gets
 * the boards, and everyone else their leave. Boards need both the
 * permission (the route's own gate) and a board, or the boards route would
 * send them straight back here.
 */
export function homeRouteFor(
  permissions: readonly string[] | null | undefined,
  hasBoards = false,
): RouteLocationRaw {
  if (canOpenWorkspace(permissions, 'engineering')) return { name: 'dashboard' }
  const boards = hasBoards && (permissions?.includes(BOARDS_VIEW) ?? false)
  return boards ? { name: 'boards' } : { name: 'leave' }
}
