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

<!-- Who can see a board, with what each choice means. Used when a board is
     created and in its settings. -->
<template>
  <fieldset class="board-vis">
    <legend class="board-vis__legend">{{ legend }}</legend>
    <v-radio-group v-model="model" hide-details :disabled="disabled">
      <v-radio value="org">
        <template #label>
          <span class="board-vis__option">
            <span>Everyone in {{ orgName }}</span>
            <span class="board-vis__note">They can view and comment. Members you add can edit.</span>
          </span>
        </template>
      </v-radio>
      <v-radio value="members">
        <template #label>
          <span class="board-vis__option">
            <span>Members only</span>
            <span class="board-vis__note">Hidden from everyone else, including search and the switcher.</span>
          </span>
        </template>
      </v-radio>
    </v-radio-group>
  </fieldset>
</template>

<script setup lang="ts">
import { useOrgName } from '@/composables/useOrgName'
import type { BoardVisibility } from '@/types/boards'

withDefaults(defineProps<{ legend?: string; disabled?: boolean }>(), {
  legend: 'Who can see it',
  disabled: false,
})
const model = defineModel<BoardVisibility>({ required: true })

const orgName = useOrgName()
</script>

<style scoped>
.board-vis {
  border: 0;
  margin: 4px 0 0;
  padding: 0;
}
.board-vis__legend {
  margin-bottom: 4px;
  font-size: 13px;
  font-weight: 600;
}
.board-vis__option {
  display: flex;
  flex-direction: column;
  padding: 4px 0;
  color: rgb(var(--v-theme-on-surface));
}
.board-vis__note {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
