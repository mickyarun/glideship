<!--
 * Copyright 2025-2026 Arun Rajkumar
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 -->

<!-- Import a Trello board into this board (Settings › Import from Trello),
     inside the board route's shell. Only the board's admins may import, as
     the server checks; anyone else is told so and sent back. -->
<template>
  <TrelloImportWizard v-if="detail && board.can('import')" :board="detail" />
  <AppPage v-else-if="detail" title="Import from Trello">
    <template #eyebrow>
      <BoardCrumbs :board="detail.board" :via="{ label: 'Settings', to: settingsRoute }" current="Import from Trello" />
    </template>
    <AppCallout variant="info" icon="mdi-lock-outline" role="note">
      {{ board.archived.value ? 'This board is archived, so nothing can be imported into it.' : "Only the board's admins can import into it." }}
      <template #actions>
        <v-btn variant="outlined" size="small" :to="settingsRoute">Back to settings</v-btn>
      </template>
    </AppCallout>
  </AppPage>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BoardCrumbs from '@/components/boards/BoardCrumbs.vue'
import TrelloImportWizard from '@/components/boards/imports/TrelloImportWizard.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import { useBoardContext } from '@/composables/useBoardContext'

const { board } = useBoardContext()
const detail = computed(() => board.detail.value)
const settingsRoute = computed(() => ({ name: 'board-settings', params: { key: detail.value?.board.key ?? '' } }))
</script>
