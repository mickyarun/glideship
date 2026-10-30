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

<!-- A board's settings, not built yet: routed already so links to it
     resolve, with a way back to the board in the meantime. -->
<template>
  <AppPage title="Board settings">
    <AppEmptyState
      icon="mdi-progress-clock"
      title="Board settings aren't available yet"
      body="Stages, members, labels and visibility will be set here."
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'board', params: { key } }">Back to the board</v-btn>
      </template>
    </AppEmptyState>
  </AppPage>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppEmptyState from '@/components/common/AppEmptyState.vue'
import AppPage from '@/components/common/AppPage.vue'
import { useBoardContext } from '@/composables/useBoardContext'

const route = useRoute()
const { board } = useBoardContext()
// The board's own key once it has loaded (the URL may differ in case).
const key = computed(() => board.detail.value?.board.key ?? String(route.params.key ?? ''))
</script>
