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

<!-- The review's options: whether archived cards come too (as archived),
     and what the import can't carry over. -->
<template>
  <AppPanel title="Options">
    <v-checkbox
      v-if="archivedCount > 0"
      :model-value="archived === 'archive'"
      density="compact"
      hide-details
      class="options__archived"
      @update:model-value="(on: boolean | null) => (archived = on ? 'archive' : 'skip')"
    >
      <template #label>Also import {{ plural(archivedCount, 'archived card') }}, as archived</template>
    </v-checkbox>
    <p class="options__note">{{ droppedLine }} Imports never start AI runs.</p>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { ArchivedChoice, DroppedCounts } from '@/types/boards'
import { plural, wordList } from '@/utils/format'

const props = defineProps<{ archivedCount: number; dropped: DroppedCounts }>()
const archived = defineModel<ArchivedChoice>('archived', { required: true })

const counted = (label: string, n: number) => (n ? `${label} (${n})` : label)
const droppedLine = computed(() => {
  const d = props.dropped
  const parts = [
    counted('custom fields', d.custom_fields),
    counted('Power-Up data', d.power_up_data),
    counted('card covers', d.covers),
  ]
  return `Not carried over: ${wordList(parts)}.`
})
</script>

<style scoped>
.options__archived :deep(.v-label) {
  font-size: 14px;
  opacity: 1;
}
.options__note {
  margin: 4px 0 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
