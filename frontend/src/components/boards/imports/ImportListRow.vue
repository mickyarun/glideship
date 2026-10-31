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
     target board, or not imported. The columns come from
     --import-list-columns, which the list's header row shares, so the
     controls carry aria-labels instead of their own floating labels.
     Stacks on phones. -->
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
      :aria-label="`What ${row.list.name} becomes`"
      density="compact"
      :error-messages="row.choice !== 'new' ? problem ?? undefined : undefined"
      :hide-details="row.choice === 'new' || !problem"
      class="list-row__choice"
    />
    <template v-if="row.choice === 'new'">
      <v-text-field
        v-model="row.name"
        :aria-label="`New stage name for ${row.list.name}`"
        placeholder="Stage name"
        :maxlength="nameMax ?? undefined"
        density="compact"
        :error-messages="problem ?? undefined"
        :hide-details="!problem"
      />
      <StageCategorySelect v-model="row.category" :aria-label="`Category for ${row.list.name}`" />
    </template>
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
import { plural } from '@/utils/format'
import { stageChoice, type ListRow, type StageOption } from '@/utils/importMapping'

const props = defineProps<{
  row: ListRow
  /** The target board's stages; empty for a new board. */
  stages: StageOption[]
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
  grid-template-columns: var(--import-list-columns);
  align-items: start;
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
  padding-top: 4px;
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
.list-row__note {
  grid-column: span 2;
  align-self: center;
}
.list-row__arrow {
  margin-top: 10px;
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (max-width: 760px) {
  .list-row {
    grid-template-columns: minmax(0, 1fr);
    gap: 8px;
  }
  .list-row__arrow {
    display: none;
  }
  .list-row__note {
    grid-column: auto;
  }
}
</style>
