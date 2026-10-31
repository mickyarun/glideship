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

// Typed calls behind a board's settings page: the board, its stages,
// members, teams, labels and linked repositories. Every write is admin-only on the server; the
// page refreshes the open board after each one.

import api from '@/services/api'
import { boardUrl } from '@/services/boardsApi'
import type {
  BoardDetail, BoardReposRead, BoardRole, LabelRead, MembersRead, RepoOptions, StageRead, TeamOptions,
} from '@/types/boards'
import type {
  BoardUpdate, LabelCreate, LabelUpdate, StageCreate, StageUpdate,
} from '@/types/boards/settings'

const stagesUrl = (key: string) => `${boardUrl(key)}/stages`
const labelsUrl = (key: string) => `${boardUrl(key)}/labels`
const reposUrl = (key: string) => `${boardUrl(key)}/repos`

export const boardSettingsApi = {
  update: async (key: string, body: BoardUpdate) =>
    (await api.patch<BoardDetail>(boardUrl(key), body)).data,
  archive: async (key: string) => (await api.post<BoardDetail>(`${boardUrl(key)}/archive`)).data,
  restore: async (key: string) => (await api.post<BoardDetail>(`${boardUrl(key)}/restore`)).data,

  createStage: async (key: string, body: StageCreate) =>
    (await api.post<StageRead>(stagesUrl(key), body)).data,
  updateStage: async (key: string, id: string, body: StageUpdate) =>
    (await api.patch<StageRead>(`${stagesUrl(key)}/${id}`, body)).data,
  reorderStages: async (key: string, stageIds: string[]) =>
    (await api.put<StageRead[]>(`${stagesUrl(key)}/order`, { stage_ids: stageIds })).data,
  /** Deletes a stage; its cards move to ``moveTo`` first (required when it has any). */
  deleteStage: async (key: string, id: string, moveTo: string | null) => {
    await api.delete(`${stagesUrl(key)}/${id}`, { params: moveTo ? { move_to: moveTo } : {} })
  },

  putMember: async (key: string, userId: string, role: BoardRole) =>
    (await api.put<MembersRead>(`${boardUrl(key)}/members/${userId}`, { role })).data,
  removeMember: async (key: string, userId: string) =>
    (await api.delete<MembersRead>(`${boardUrl(key)}/members/${userId}`)).data,
  putTeam: async (key: string, teamId: string, role: BoardRole) =>
    (await api.put<MembersRead>(`${boardUrl(key)}/teams/${teamId}`, { role })).data,
  /** The org's active teams with their sizes, for a board admin's team picker. */
  teamOptions: async (key: string) => (await api.get<TeamOptions>(`${boardUrl(key)}/teams/options`)).data,
  removeTeam: async (key: string, teamId: string) =>
    (await api.delete<MembersRead>(`${boardUrl(key)}/teams/${teamId}`)).data,

  createLabel: async (key: string, body: LabelCreate) =>
    (await api.post<LabelRead>(labelsUrl(key), body)).data,
  updateLabel: async (key: string, id: string, body: LabelUpdate) =>
    (await api.patch<LabelRead>(`${labelsUrl(key)}/${id}`, body)).data,
  deleteLabel: async (key: string, id: string) => {
    await api.delete(`${labelsUrl(key)}/${id}`)
  },

  /** The org's active repositories, each saying whether the board links it. */
  repoOptions: async (key: string) => (await api.get<RepoOptions>(`${reposUrl(key)}/options`)).data,
  /** Link a repository; the reply is the board's linked list. */
  linkRepo: async (key: string, repoId: string) =>
    (await api.put<BoardReposRead>(`${reposUrl(key)}/${repoId}`)).data,
  /** Unlink a repository; cards naming it lose it. The reply is the linked list. */
  unlinkRepo: async (key: string, repoId: string) =>
    (await api.delete<BoardReposRead>(`${reposUrl(key)}/${repoId}`)).data,
}
