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

<!-- A board route that the API answered with 404: the board (or the card
     on it) doesn't exist, or it's members-only and I'm not a member. The
     API doesn't say which, so neither does this page. -->
<template>
  <AppPage :title="`${what === 'card' ? 'Card' : 'Board'} not found`">
    <AppEmptyState
      icon="mdi-lock-outline"
      :title="`This ${what} doesn't exist, or you don't have access`"
      body="If someone sent you a link, ask them to add you to the board."
    >
      <template #actions>
        <v-btn color="primary" :to="{ name: 'boards' }">Go to your boards</v-btn>
        <v-btn variant="outlined" @click="switcher.show()">Find a board</v-btn>
      </template>
    </AppEmptyState>
  </AppPage>
</template>

<script setup lang="ts">
import AppEmptyState from '@/components/common/AppEmptyState.vue'
import AppPage from '@/components/common/AppPage.vue'
import { useBoardSwitcher } from '@/composables/useBoardSwitcher'

withDefaults(defineProps<{ what?: 'board' | 'card' }>(), { what: 'board' })

const switcher = useBoardSwitcher()
</script>
