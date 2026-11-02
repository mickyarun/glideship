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
 * Team boards, open to anyone holding ``boards:view`` in either workspace
 * (no ``meta.workspace``). Which boards someone may open, and what they
 * may do on one, is the API's call: a board they can't see is a 404.
 */
import type { RouteRecordRaw } from 'vue-router'
import { DELIVERY_BOARD } from '@/constants/boards'
import { BOARDS_CREATE, BOARDS_VIEW } from '@/utils/workspace'

const meta = { permission: BOARDS_VIEW }

export const boardRoutes: RouteRecordRaw[] = [
  {
    path: 'boards',
    name: 'boards',
    meta,
    component: () => import('@/views/boards/BoardsIndexView.vue'),
  },
  // Importing into a new board needs boards:create, as the server checks.
  // ``imports`` is a reserved board key, so this never shadows a board.
  {
    path: 'boards/imports/trello',
    name: 'board-import-new',
    meta: { permission: BOARDS_CREATE },
    component: () => import('@/views/boards/NewBoardImportView.vue'),
  },
  // The Delivery board's key, typed as a board address, opens the BUD board.
  { path: `boards/${DELIVERY_BOARD.key}`, redirect: DELIVERY_BOARD.path },
  {
    // The shell loads the board and follows its live channel once; the
    // board, a card and the settings are its child pages.
    path: 'boards/:key',
    meta,
    component: () => import('@/views/boards/BoardShell.vue'),
    children: [
      { path: '', name: 'board', component: () => import('@/views/boards/BoardView.vue') },
      {
        path: 'settings',
        name: 'board-settings',
        component: () => import('@/views/boards/BoardSettingsView.vue'),
      },
      {
        // Anyone who can open the board reads its metrics.
        path: 'metrics',
        name: 'board-metrics',
        component: () => import('@/views/boards/BoardMetricsView.vue'),
      },
      {
        // Board admins only; the page says so to anyone else.
        path: 'settings/import',
        name: 'board-import',
        component: () => import('@/views/boards/BoardImportView.vue'),
      },
      {
        path: 'cards/:number',
        name: 'board-card',
        component: () => import('@/views/boards/BoardCardView.vue'),
      },
    ],
  },
]
