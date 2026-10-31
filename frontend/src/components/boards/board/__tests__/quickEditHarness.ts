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

// A board card tile as the board renders it, for the quick-edit specs: the
// board context (capabilities, members, the people who can be assigned,
// the linked repositories, the real cards store holding the card in a
// loaded column) provided above it. The card API and the member
// directory are mocked by each spec.

import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { EDITOR_CAPS, makeCard, makeDetail, makeStage } from '@/components/boards/__tests__/fixtures'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import BoardCardTile from '@/components/boards/board/BoardCardTile.vue'
import { provideBoardContext } from '@/composables/useBoardContext'
import type { BoardPage } from '@/composables/useBoardPage'
import { useBoardPeople } from '@/composables/useBoardPeople'
import { useBoardRepos } from '@/composables/useBoardRepos'
import { useBoardCardsStore } from '@/stores/boardCards'
import type {
  BoardAction, BoardPersonRead, BoardRepoRead, BoardVisibility, CardSummary, MemberRead,
} from '@/types/boards'

export const MEMBERS: MemberRead[] = [
  { user_id: 'u1', name: 'Asha Rao', avatar_url: null, role: 'editor' },
  { user_id: 'u2', name: 'Ben Lim', avatar_url: null, role: 'admin' },
]

/** GET /boards/{key}/people for the same board: the members, as their own rows. */
export const PEOPLE: BoardPersonRead[] = MEMBERS.map(m => ({
  id: m.user_id, name: m.name, avatar_url: m.avatar_url, role: m.role, via: 'member', team_name: null,
}))

interface TileOptions {
  card?: Partial<CardSummary>
  capabilities?: BoardAction[]
  visibility?: BoardVisibility
  people?: BoardPersonRead[]
  repos?: BoardRepoRead[]
}

export async function mountTile({
  card = {}, capabilities = EDITOR_CAPS, visibility = 'members', people = PEOPLE, repos = [],
}: TileOptions = {}) {
  const { plugins } = boardTestPlugins()
  const store = useBoardCardsStore()
  const stage = makeStage('s1')
  store.reset('SEO', 'b1', [stage])
  const column = store.columns.s1
  column.items = [makeCard('3', { key: 'SEO-3', number: 3, ...card })]
  column.loaded = true
  const detail = ref(makeDetail({ capabilities, board: { ...makeDetail().board, key: 'SEO', visibility } }))
  const boardPeople = useBoardPeople()
  boardPeople.people.value = people
  const boardRepos = useBoardRepos()
  boardRepos.set(repos)
  const page = {
    board: { detail, can: (a: BoardAction) => capabilities.includes(a), archived: ref(false) },
    cards: store,
    members: ref(MEMBERS),
    people: boardPeople,
    repos: boardRepos,
  } as unknown as BoardPage

  const failures: string[] = []
  const Host = defineComponent({
    setup() {
      provideBoardContext(page)
      return () =>
        h(BoardCardTile, {
          card: store.columns.s1.items[0],
          boardKey: 'SEO',
          stages: [stage],
          labelsById: new Map(),
          now: new Date('2026-10-20T12:00:00Z'),
          canMove: true,
          canArchive: true,
          onFailed: (error: string) => failures.push(error),
        })
    },
  })
  const wrapper = mount(Host, { global: { plugins: plugins as never[] }, attachTo: document.body })
  await flushPromises()
  /** The card as the store holds it now. */
  const held = () => store.columns.s1.items[0]
  return { wrapper, store, held, failures }
}

/** Open a quick-edit menu by its button's accessible name. */
export async function openBy(label: string): Promise<HTMLElement> {
  const button = document.querySelector<HTMLElement>(`button[aria-label^="${label}"]`)
  if (!button) throw new Error(`No button labelled ${label}`)
  button.click()
  await flushPromises()
  return button
}
