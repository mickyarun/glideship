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

<!-- Where the import goes, from Boards › Import from Trello: a new board
     (this page), or a board I admin, which opens that board's own import
     page (its stages are what lists map into). -->
<template>
  <div class="target-choice">
    <span :id="labelId" class="target-choice__label">Import into</span>
    <AppPillToggle v-model="into" :options="OPTIONS" :aria-labelledby="labelId" />
    <template v-if="into === 'existing'">
      <v-progress-linear v-if="store.loading" indeterminate color="primary" aria-label="Loading your boards" />
      <AppCallout v-else-if="store.error" variant="error" role="alert">
        {{ store.error }}
        <template #actions>
          <v-btn variant="outlined" size="small" @click="store.fetchIndex()">Try again</v-btn>
        </template>
      </AppCallout>
      <p v-else-if="!adminBoards.length" class="target-choice__note">
        You don't admin any boards. Import into a new board, or ask a board's admin to import into theirs.
      </p>
      <v-select
        v-else
        :items="adminBoards"
        item-title="name"
        item-value="key"
        label="Board"
        density="compact"
        hide-details
        class="target-choice__board"
        @update:model-value="open"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import { useBoardsStore } from '@/stores/boards'
import type { CustomBoardItem } from '@/types/boards'
import { importPath } from '@/utils/boardSettingsSections'

type Into = 'new' | 'existing'
const OPTIONS: { label: string; value: Into }[] = [
  { label: 'A new board', value: 'new' },
  { label: 'A board you admin', value: 'existing' },
]

const router = useRouter()
const store = useBoardsStore()
const labelId = useId()
const into = ref<Into>('new')

const adminBoards = computed(() =>
  store.items.filter((b): b is CustomBoardItem => b.kind === 'custom' && b.role === 'admin'),
)

watch(into, value => {
  if (value === 'existing' && !store.loaded && !store.loading) void store.fetchIndex()
})

function open(key: string | null): void {
  if (key) void router.push(importPath(key))
}
</script>

<style scoped>
.target-choice {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 12px;
}
.target-choice__label {
  font-size: 14px;
  font-weight: 600;
}
.target-choice__board {
  flex: 0 1 320px;
}
.target-choice__note {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
