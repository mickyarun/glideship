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

// The Trello import wizard: a session (followed live), the Trello
// connection, the people a member may map to, and the review form. The
// session id rides in the URL (?session=) both ways, so leaving and coming
// back, a reload or a link lands on the same import at its current step.
// Opened without one, it offers the import I left open instead.

import { computed, onMounted, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useImportMappingForm, type PickablePerson } from '@/composables/useImportMappingForm'
import { useImportSession } from '@/composables/useImportSession'
import { useMemberDirectory } from '@/composables/useMemberDirectory'
import { useOpenImports } from '@/composables/useOpenImports'
import { usePermissions } from '@/composables/usePermissions'
import { useTrelloConnection } from '@/composables/useTrelloConnection'
import { boardImportsApi } from '@/services/boardImportsApi'
import { boardsApi } from '@/services/boardsApi'
import { useBoardsStore } from '@/stores/boards'
import type { BoardDetail } from '@/types/boards'
import { failureLog } from '@/utils/importErrors'

export const SESSION_QUERY_KEY = 'session'

const PEOPLE_FAILED = "Couldn't load the people to match members to. Suggestions stay; try again to pick others."
const ACTIVE = ['pending', 'parsing', 'running']

export function useTrelloImportWizard(board: Ref<BoardDetail | null>, hooks: { onStagesStale?: () => void } = {}) {
  const route = useRoute()
  const router = useRouter()
  const boards = useBoardsStore()
  const directory = useMemberDirectory()
  const { hasPermission } = usePermissions()
  const imp = useImportSession()
  const connection = useTrelloConnection()
  const open = useOpenImports(computed(() => board.value?.board.id ?? null))
  const canConnect = computed(() => hasPermission('integrations:configure'))
  const limits = computed(() => boards.limits)
  const via = ref<'upload' | 'api'>('upload')
  const starting = ref(false)

  // Existing board: who can open it. New board: the org's members (the
  // server keeps it to people who can view boards). Null until known.
  const boardPeople = ref<PickablePerson[] | null>(null)
  const peopleError = ref('')
  const people = computed<PickablePerson[] | null>(() =>
    board.value ? boardPeople.value : directory.entries.value.length ? directory.entries.value : null,
  )
  async function loadPeople(): Promise<void> {
    peopleError.value = ''
    const key = board.value?.board.key
    if (!key) {
      await directory.ensureLoaded()
      if (!directory.entries.value.length) peopleError.value = PEOPLE_FAILED
      return
    }
    try {
      boardPeople.value = (await boardsApi.people(key)).items.map(p => ({ id: p.id, name: p.name }))
    } catch (err) {
      console.error('[imports] board people fetch failed:', failureLog(err))
      peopleError.value = PEOPLE_FAILED
    }
  }
  const retryPeople = async () => {
    peopleError.value = ''
    if (!board.value) await directory.ensureLoaded(true)
    await loadPeople()
  }

  const form = useImportMappingForm(imp.session, {
    existingKey: computed(() => board.value?.board.key ?? null),
    stages: computed(() => board.value?.stages ?? []),
    people,
    limits: computed(() => ({
      nameMax: limits.value?.stage_name_max ?? null,
      maxStages: limits.value?.max_stages ?? null,
    })),
  })

  const queryId = () => {
    const id = route.query[SESSION_QUERY_KEY]
    return typeof id === 'string' && id ? id : null
  }
  // The URL follows the session, and the session follows the URL.
  watch(() => imp.session.value?.id ?? null, id => {
    if (queryId() === id) return
    void router.replace({ query: { ...route.query, [SESSION_QUERY_KEY]: id ?? undefined } })
  })
  watch(queryId, id => {
    if (id === (imp.session.value?.id ?? null)) return
    if (id) return void imp.load(id)
    imp.reset()
    void offerOpen()
  })

  // A run into a new board that stopped part-way made that board: its review
  // continues on the board's own import page, mapping into its stages.
  watch(() => imp.session.value, s => {
    if (board.value || s?.status !== 'ready' || !s.board_id || !s.board_key) return
    void router.replace({ name: 'board-import', params: { key: s.board_key }, query: { [SESSION_QUERY_KEY]: s.id } })
  })

  /** Without ?session=: show this board's running import, or offer the one I left open. */
  async function offerOpen(): Promise<void> {
    const found = await open.check()
    if (!found || imp.session.value) return
    if (board.value && found.board_id === board.value.board.id && ACTIVE.includes(found.status)) {
      return void imp.load(found.id)
    }
    open.offer.value = found
  }
  function continueOpen(): void {
    const id = open.offer.value?.id
    open.offer.value = null
    if (id) void imp.load(id)
  }

  const upload = (file: File) => {
    via.value = 'upload'
    return imp.queue(() => boardImportsApi.upload(file), "Couldn't upload that file. Try again.")
  }
  const readFromTrello = (trelloBoardId: string) => {
    via.value = 'api'
    return imp.queue(() => boardImportsApi.fromTrello(trelloBoardId), "Couldn't read that board from Trello. Try again.")
  }

  /** Save the review, then start the import; once, however often it's clicked. */
  async function startImport(): Promise<void> {
    const id = imp.session.value?.id
    if (!id || imp.step.value !== 'map' || !form.valid.value || starting.value || imp.busy.value) return
    if (imp.countdown.waiting.value) return
    starting.value = true
    imp.failure.value = null
    form.showRefusal(null)
    try {
      try {
        imp.session.value = await boardImportsApi.saveMapping(id, form.mapping())
      } catch (err) {
        imp.fail(err, "Couldn't save the review. Check it and try again.")
        form.showRefusal(imp.failure.value)
        return
      }
      await imp.start()
    } finally {
      starting.value = false
    }
  }

  /** Discard this import (?session= goes with it) and choose a source again. */
  const startOver = () => (imp.session.value ? imp.discard() : Promise.resolve(imp.reset()))

  /** Back to the review of a stopped import, with the board's stages read again. */
  async function reviewAgain(): Promise<void> {
    if (await imp.review()) hooks.onStagesStale?.()
  }

  const boardName = computed(() => {
    const target = imp.session.value?.mapping?.target
    return board.value?.board.name ?? (target?.kind === 'new' ? target.name : imp.session.value?.board_key ?? 'The board')
  })

  onMounted(() => {
    void boards.ensureLimits()
    void loadPeople()
    const id = queryId()
    if (id) void imp.load(id)
    else void offerOpen()
  })

  return {
    imp, connection, form, people, peopleError, open, canConnect, limits, via, starting, boardName,
    upload, readFromTrello, startImport, startOver, reviewAgain, retryPeople, continueOpen,
  }
}
