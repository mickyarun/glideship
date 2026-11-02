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

// Who holds a role on a board, and who can see it: people from the org
// directory and teams, each with a role, plus the board's visibility. The
// list reloads when someone else changes it (``member_changed``), and each
// change's reply becomes the list, here and on the board.

import { computed, onMounted, ref, watch } from 'vue'
import type { BoardPage } from '@/composables/useBoardPage'
import type { BoardSettingsStatus } from '@/composables/useBoardSettingsStatus'
import { useMemberDirectory } from '@/composables/useMemberDirectory'
import { useTopicChannel } from '@/composables/useTopicChannel'
import { ROLE_LABELS } from '@/constants/boards'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { boardsApi } from '@/services/boardsApi'
import {
  boardTopic, type BoardRole, type BoardSocketMessage, type BoardVisibility, type MembersRead, type TeamOption,
} from '@/types/boards'
import { extractApiError } from '@/utils/errors'
import { plural } from '@/utils/format'
import { logFailure } from '@/utils/logFailure'

export type GrantKind = 'person' | 'team'

/** A person or team holding a role on the board. */
export interface Grant {
  kind: GrantKind
  id: string
  name: string
  role: BoardRole
  avatarUrl: string | null
  /** A team's size, when known. */
  memberCount?: number | null
}

/** Someone who could be given a role: an org member or a team. */
export interface GrantCandidate {
  value: string
  kind: GrantKind
  id: string
  title: string
  subtitle: string
}

export function useMemberSettings(page: BoardPage, status: BoardSettingsStatus) {
  const grants = ref<MembersRead>({ members: [], teams: [] })
  const loading = ref(false)
  const loadError = ref('')
  const directory = useMemberDirectory()
  // The org's teams come from the board (for its admins), whatever workspace they're in.
  const teamOptions = ref<TeamOption[]>([])
  const canListTeams = computed(() => page.board.can('manage_members'))
  const detail = computed(() => page.board.detail.value)
  let seq = 0

  async function load(): Promise<void> {
    const key = detail.value?.board.key
    if (!key) return
    const mine = ++seq
    loading.value = true
    try {
      const reply = await boardsApi.members(key)
      if (mine === seq) {
        grants.value = reply
        loadError.value = ''
      }
    } catch (err) {
      if (mine === seq) loadError.value = extractApiError(err, "Couldn't load this board's members.")
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  async function loadTeams(): Promise<void> {
    const key = detail.value?.board.key
    if (!key) return
    try {
      teamOptions.value = (await boardSettingsApi.teamOptions(key)).items
    } catch (err) {
      // Without the list people can still be added; teams can't.
      logFailure('boards', 'team options fetch', err)
    }
  }

  const topic = computed(() => (detail.value ? boardTopic(detail.value.board.id) : null))
  useTopicChannel<BoardSocketMessage>(topic, { member_changed: () => void load() }, () => void load(), {
    ignoreOwn: true,
  })
  watch(() => detail.value?.board.key, () => void load(), { immediate: true })
  onMounted(() => {
    void directory.ensureLoaded()
    if (canListTeams.value) void loadTeams()
  })

  const rows = computed<Grant[]>(() => [
    ...grants.value.members.map(m => ({
      kind: 'person' as const, id: m.user_id, name: m.name, role: m.role, avatarUrl: m.avatar_url,
    })),
    ...grants.value.teams.map(t => ({
      kind: 'team' as const, id: t.team_id, name: t.name, role: t.role, avatarUrl: null,
      memberCount: teamOptions.value.find(o => o.id === t.team_id)?.member_count ?? null,
    })),
  ])

  /** The one admin row left, which the server won't let go. */
  const lastAdmin = computed(() => {
    const admins = rows.value.filter(r => r.role === 'admin')
    return admins.length === 1 ? admins[0] : null
  })

  const candidates = computed<GrantCandidate[]>(() => {
    const people = new Set(grants.value.members.map(m => m.user_id))
    const onBoard = new Set(grants.value.teams.map(t => t.team_id))
    return [
      ...directory.entries.value
        .filter(e => !people.has(e.id))
        .map(e => ({ value: `person:${e.id}`, kind: 'person' as const, id: e.id, title: e.name, subtitle: e.email })),
      ...teamOptions.value
        .filter(t => !onBoard.has(t.id))
        .map(t => ({
          value: `team:${t.id}`, kind: 'team' as const, id: t.id, title: t.name,
          subtitle: `Team · ${plural(t.member_count, 'person', 'people')}`,
        })),
    ]
  })

  function apply(reply: MembersRead): void {
    // Newer than any load on its way, which mustn't land over it.
    seq++
    loading.value = false
    grants.value = reply
    page.members.value = reply.members
  }

  function put(kind: GrantKind, id: string, role: BoardRole, done: string): Promise<boolean> {
    return status.run(async key => {
      apply(kind === 'person'
        ? await boardSettingsApi.putMember(key, id, role)
        : await boardSettingsApi.putTeam(key, id, role))
    }, done)
  }

  function add(candidate: GrantCandidate, role: BoardRole): Promise<boolean> {
    return put(candidate.kind, candidate.id, role, `Added ${candidate.title} as ${ROLE_LABELS[role]}`)
  }

  function setRole(grant: Grant, role: BoardRole): Promise<boolean> {
    if (role === grant.role) return Promise.resolve(true)
    return put(grant.kind, grant.id, role, `${grant.name} is now ${ROLE_LABELS[role]}`)
  }

  function remove(grant: Grant): Promise<boolean> {
    return status.run(async key => {
      apply(grant.kind === 'person'
        ? await boardSettingsApi.removeMember(key, grant.id)
        : await boardSettingsApi.removeTeam(key, grant.id))
    }, `Removed ${grant.name}`)
  }

  function setVisibility(visibility: BoardVisibility): Promise<boolean> {
    if (visibility === detail.value?.board.visibility) return Promise.resolve(true)
    const done = visibility === 'members' ? 'Only members can see this board now' : 'Everyone in the org can see this board now'
    return status.run(async key => {
      page.board.replace(await boardSettingsApi.update(key, { visibility }))
    }, done, { refresh: false })
  }

  return {
    rows, loading, loadError, lastAdmin, candidates, canListTeams,
    load, add, setRole, remove, setVisibility,
  }
}

export type MemberSettings = ReturnType<typeof useMemberSettings>
