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
// session id rides in the URL (?session=) so leaving and coming back, or
// a reload, lands on the same import at its current step.

import { computed, onMounted, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useImportMappingForm, type PickablePerson } from '@/composables/useImportMappingForm'
import { useImportSession } from '@/composables/useImportSession'
import { useMemberDirectory } from '@/composables/useMemberDirectory'
import { usePermissions } from '@/composables/usePermissions'
import { useTrelloConnection } from '@/composables/useTrelloConnection'
import { boardImportsApi } from '@/services/boardImportsApi'
import { boardsApi } from '@/services/boardsApi'
import { useBoardsStore } from '@/stores/boards'
import type { BoardDetail } from '@/types/boards'

export const SESSION_QUERY_KEY = 'session'

export function useTrelloImportWizard(board: Ref<BoardDetail | null>) {
  const route = useRoute()
  const router = useRouter()
  const boards = useBoardsStore()
  const directory = useMemberDirectory()
  const { hasPermission } = usePermissions()
  const imp = useImportSession()
  const connection = useTrelloConnection()
  const canConnect = computed(() => hasPermission('integrations:configure'))
  const limits = computed(() => boards.limits)
  const via = ref<'upload' | 'api'>('upload')
  const saving = ref(false)

  // Existing board: who can open it. New board: the org's members (the
  // server keeps it to people who can view boards).
  const boardPeople = ref<PickablePerson[] | null>(null)
  const people = computed<PickablePerson[] | null>(() =>
    board.value ? boardPeople.value : directory.entries.value.length ? directory.entries.value : null,
  )
  async function loadPeople(): Promise<void> {
    const key = board.value?.board.key
    if (!key) return void directory.ensureLoaded()
    try {
      boardPeople.value = (await boardsApi.people(key)).items.map(p => ({ id: p.id, name: p.name }))
    } catch (err) {
      console.error('[imports] board people fetch failed:', err)
      boardPeople.value = []
    }
  }

  const form = useImportMappingForm(imp.session, {
    existingKey: computed(() => board.value?.board.key ?? null),
    stages: computed(() => board.value?.stages ?? []),
    people,
    stageNameMax: computed(() => limits.value?.stage_name_max ?? null),
  })

  // The URL follows the session, so the page can be left and found again.
  watch(() => imp.session.value?.id ?? null, id => {
    if ((route.query[SESSION_QUERY_KEY] ?? null) === id) return
    void router.replace({ query: { ...route.query, [SESSION_QUERY_KEY]: id ?? undefined } })
  })

  const upload = (file: File) => {
    via.value = 'upload'
    return imp.queue(() => boardImportsApi.upload(file), "Couldn't upload that file. Try again.")
  }
  const readFromTrello = (trelloBoardId: string) => {
    via.value = 'api'
    return imp.queue(() => boardImportsApi.fromTrello(trelloBoardId), "Couldn't read that board from Trello. Try again.")
  }

  /** Save the review, then start the import. */
  async function startImport(): Promise<void> {
    const id = imp.session.value?.id
    if (!id || !form.valid.value || saving.value || imp.countdown.waiting.value) return
    saving.value = true
    imp.failure.value = null
    try {
      imp.session.value = await boardImportsApi.saveMapping(id, form.mapping())
    } catch (err) {
      imp.fail(err, "Couldn't save the review. Check it and try again.")
      return
    } finally {
      saving.value = false
    }
    await imp.start()
  }

  /** Leave this session (it expires on its own) and choose a source again. */
  function startOver(): void {
    imp.reset()
  }

  const boardName = computed(() => {
    const target = imp.session.value?.mapping?.target
    return board.value?.board.name ?? (target?.kind === 'new' ? target.name : imp.session.value?.board_key ?? 'The board')
  })

  onMounted(() => {
    void boards.ensureLimits()
    void loadPeople()
    const id = route.query[SESSION_QUERY_KEY]
    if (typeof id === 'string' && id) void imp.load(id)
  })

  return {
    imp, connection, form, people, canConnect, limits, via, saving, boardName,
    upload, readFromTrello, startImport, startOver,
  }
}
