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

<!-- A new board's name and key side by side, with what the key will do
     under them. The fields come from useBoardKeyFields; the lengths from
     the server's board limits. -->
<template>
  <div>
    <div class="name-key__row">
      <v-text-field
        v-model="fields.name.value"
        label="Name"
        :autofocus="autofocus"
        :maxlength="limits?.board_name_max"
        hide-details="auto"
      />
      <v-text-field
        :model-value="fields.key.value"
        label="Key"
        class="name-key__key"
        :maxlength="limits?.board_key_max"
        :aria-describedby="hintId"
        hide-details
        @update:model-value="fields.setKey"
      />
    </div>
    <p :id="hintId" class="name-key__hint">{{ fields.keyHint.value }}</p>
  </div>
</template>

<script setup lang="ts">
import { useId } from 'vue'
import type { BoardKeyFields } from '@/composables/useBoardKeyFields'
import type { BoardLimits } from '@/types/boards'

withDefaults(
  defineProps<{
    fields: Pick<BoardKeyFields, 'name' | 'key' | 'keyHint' | 'setKey'>
    limits: BoardLimits | null
    autofocus?: boolean
  }>(),
  { autofocus: false },
)

const hintId = useId()
</script>

<style scoped>
/* Top-aligned so the name field keeps its own height next to the key. */
.name-key__row {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  align-items: start;
  gap: 12px;
}
.name-key__hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.name-key__key :deep(input) {
  font-family: var(--font-mono);
  text-transform: uppercase;
}
@media (max-width: 600px) {
  .name-key__row {
    grid-template-columns: 1fr;
  }
}
</style>
