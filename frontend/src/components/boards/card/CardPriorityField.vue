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

<!-- A card's priority in its details panel: the tag (or None), and for
     editors a Change link like the panel's other rows, opening P0–P3 and
     No priority. -->
<template>
  <BudPriorityChip v-if="priority" :priority="priority" />
  <span v-else class="priority-field__none">None</span>
  <v-menu v-if="editable" location="bottom end">
    <template #activator="{ props: menuProps }">
      <button v-bind="menuProps" type="button" class="priority-field__link" aria-label="Change priority">Change</button>
    </template>
    <v-list density="compact" min-width="160" aria-label="Priority">
      <v-list-item v-for="p in BUD_PRIORITIES" :key="p" :active="priority === p" :title="p" @click="emit('change', p)" />
      <v-list-item v-if="priority" title="No priority" @click="emit('change', null)" />
    </v-list>
  </v-menu>
</template>

<script setup lang="ts">
import BudPriorityChip from '@/components/buds/BudPriorityChip.vue'
import { BUD_PRIORITIES, type BUDPriority } from '@/types'

defineProps<{ priority: BUDPriority | null; editable: boolean }>()
const emit = defineEmits<{ change: [priority: BUDPriority | null] }>()
</script>

<style scoped>
.priority-field__none {
  color: rgb(var(--v-theme-on-surface-variant));
}
.priority-field__link {
  border: 0;
  padding: 0;
  background: transparent;
  font: inherit;
  font-size: 13px;
  color: var(--color-accent-text);
  cursor: pointer;
}
.priority-field__link:hover {
  text-decoration: underline;
}
.priority-field__link:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
@media (pointer: coarse) {
  .priority-field__link {
    min-height: 44px;
  }
}
</style>
