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

// The open board, shared from the board route's shell (views/boards/
// BoardShell.vue) with its child pages (the board, a card, settings), so
// the board and its live channel are set up once however the pages change.

import { inject, provide, type InjectionKey } from 'vue'
import type { BoardPage } from '@/composables/useBoardPage'

const KEY: InjectionKey<BoardPage> = Symbol('board-page')

export function provideBoardContext(page: BoardPage): void {
  provide(KEY, page)
}

export function useBoardContext(): BoardPage {
  const page = inject(KEY)
  if (!page) throw new Error('useBoardContext() needs the board route shell above it')
  return page
}
