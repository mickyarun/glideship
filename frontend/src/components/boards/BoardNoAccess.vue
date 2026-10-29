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

<!-- A board route that the API answered with 404: the board doesn't exist,
     or it's members-only and I'm not a member. The API doesn't say which,
     so neither does this page. -->
<template>
  <AppPage title="Board not found">
    <AppEmptyState
      icon="mdi-lock-outline"
      title="This board doesn't exist, or you don't have access to it"
      body="Members-only boards are visible to their members. Ask the person who shared the link to add you."
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'boards' }">All boards</v-btn>
        <v-btn variant="outlined" @click="switcher.show()">Find a board</v-btn>
      </template>
    </AppEmptyState>
  </AppPage>
</template>

<script setup lang="ts">
import AppEmptyState from '@/components/common/AppEmptyState.vue'
import AppPage from '@/components/common/AppPage.vue'
import { useBoardSwitcher } from '@/composables/useBoardSwitcher'

const switcher = useBoardSwitcher()
</script>
