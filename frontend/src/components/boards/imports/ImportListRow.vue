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

<!-- One Trello list and what it becomes: a new stage (its name and
     category, guessed from the list's name), an existing stage of the
     target board, or not imported. Stacks on phones. -->
<template>
  <div class="list-row" role="group" :aria-label="`List ${row.list.name}`">
    <div class="list-row__source">
      <span class="list-row__name">{{ row.list.name }}</span>
      <span class="list-row__meta">
        {{ plural(row.list.card_count, 'card') }}<template v-if="row.list.closed"> · archived list</template>
      </span>
    </div>
    <v-icon class="list-row__arrow" icon="mdi-arrow-right" size="16" aria-hidden="true" />
    <v-select
      v-model="row.choice"
      :items="choices"
      label="Becomes"
      density="compact"
      hide-details
      class="list-row__choice"
    />
    <div v-if="row.choice === 'new'" class="list-row__new">
      <v-text-field
        v-model="row.name"
        label="Stage name"
        :maxlength="nameMax ?? undefined"
        density="compact"
        :error-messages="problem ?? undefined"
        :hide-details="!problem"
      />
      <StageCategorySelect v-model="row.category" :aria-label="`Category for ${row.list.name}`" />
    </div>
    <div v-else class="list-row__note">
      <AppTag v-if="existing" :color="CATEGORY_COLORS[existing.category]">{{ CATEGORY_LABELS[existing.category] }}</AppTag>
      <span v-else>Not imported</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import StageCategorySelect from '@/components/boards/settings/StageCategorySelect.vue'
import AppTag from '@/components/common/AppTag.vue'
import { CATEGORY_COLORS, CATEGORY_LABELS } from '@/constants/boards'
import type { StageRead } from '@/types/boards'
import { plural } from '@/utils/format'
import { stageChoice, type ListRow } from '@/utils/importMapping'

const props = defineProps<{
  row: ListRow
  /** The target board's stages; empty for a new board. */
  stages: Pick<StageRead, 'id' | 'name' | 'category'>[]
  problem: string | null
  nameMax: number | null
}>()

const choices = computed(() => [
  { title: 'New stage', value: 'new' },
  ...props.stages.map(s => ({ title: `Into ${s.name}`, value: stageChoice(s.id) })),
  { title: "Don't import", value: 'skip' },
])
const existing = computed(() => props.stages.find(s => stageChoice(s.id) === props.row.choice) ?? null)
</script>

<style scoped>
.list-row {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) 16px minmax(136px, 1fr) minmax(0, 1.9fr);
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid rgb(var(--v-theme-rule));
}
.list-row:last-child {
  border-bottom: 0;
}
.list-row__source {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.list-row__name {
  font-size: 14px;
  overflow-wrap: anywhere;
}
.list-row__meta,
.list-row__note {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.list-row__arrow {
  color: rgb(var(--v-theme-on-surface-variant));
}
.list-row__new {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(140px, auto);
  gap: 8px;
  align-items: start;
}
@media (max-width: 760px) {
  .list-row {
    grid-template-columns: minmax(0, 1fr);
    gap: 8px;
  }
  .list-row__arrow {
    display: none;
  }
  .list-row__new {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
