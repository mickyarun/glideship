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

<!-- One card on a team board. The title link stretches over the card, so
     the ⋯ menu sits above it and stays separately clickable without
     nesting interactive elements. Same rhythm as the BUD board card. -->
<template>
  <article class="card-tile" :data-card-id="card.id">
    <div class="card-tile__top">
      <span class="card-tile__key">{{ card.key }}</span>
      <BudPriorityChip v-if="card.priority" :priority="card.priority" />
      <BoardCardMenu
        class="card-tile__menu"
        :card="card"
        :stages="stages"
        :board-key="boardKey"
        :can-move="canMove"
        :can-archive="canArchive"
        @move="(stageId) => emit('move', card, stageId)"
        @archive="emit('archive', card)"
      />
    </div>

    <h3 class="card-tile__title">
      <router-link :to="cardRoute" class="card-tile__link" draggable="false">{{ card.title }}</router-link>
    </h3>

    <div v-if="labels.length" class="card-tile__labels">
      <AppTag v-for="label in labels" :key="label.id" :color="labelColor(label.color)" sr-prefix="Label">
        {{ label.name }}
      </AppTag>
    </div>

    <div v-if="date || card.checklist_total || card.assignee_ids.length" class="card-tile__foot">
      <span v-if="date" class="card-tile__date" :class="`card-tile__date--${date.tone}`">
        <v-icon :icon="date.icon" size="14" aria-hidden="true" />{{ date.text }}
      </span>
      <span
        v-if="card.checklist_total"
        class="card-tile__checklist"
        :aria-label="`Checklist ${card.checklist_done} of ${card.checklist_total} done`"
      >
        <v-icon icon="mdi-checkbox-marked-outline" size="14" aria-hidden="true" />
        {{ card.checklist_done }}/{{ card.checklist_total }}
      </span>
      <span class="card-tile__people">
        <AppMonogram
          v-for="id in card.assignee_ids"
          :key="id"
          :name="nameFor(id)"
          :src="photoFor(id)"
          :size="22"
          :title="nameFor(id)"
          :label="`Assigned to ${nameFor(id)}`"
        />
      </span>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BoardCardMenu from '@/components/boards/board/BoardCardMenu.vue'
import BudPriorityChip from '@/components/buds/BudPriorityChip.vue'
import AppMonogram from '@/components/common/AppMonogram.vue'
import AppTag from '@/components/common/AppTag.vue'
import { useMemberDirectory } from '@/composables/useMemberDirectory'
import { labelColor } from '@/constants/boards'
import type { CardSummary, LabelRead, StageRead } from '@/types/boards'
import { dateChip } from '@/utils/boardFilters'

const props = defineProps<{
  card: CardSummary
  boardKey: string
  stages: StageRead[]
  labelsById: Map<string, LabelRead>
  now: Date
  canMove: boolean
  canArchive: boolean
}>()

const emit = defineEmits<{
  move: [card: CardSummary, stageId: string]
  archive: [card: CardSummary]
}>()

const { nameFor, photoFor } = useMemberDirectory()

const cardRoute = computed(() => ({
  name: 'board-card',
  params: { key: props.boardKey, number: props.card.number },
}))
const labels = computed(() =>
  props.card.label_ids.map(id => props.labelsById.get(id)).filter((l): l is LabelRead => !!l),
)
const date = computed(() => dateChip(props.card, props.now))
</script>

<style scoped>
.card-tile {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: var(--radius-card);
  transition: border-color var(--dur-short) var(--ease-out);
}
.card-tile:hover,
.card-tile:focus-within {
  border-color: rgba(var(--v-theme-primary), 0.55);
}
.card-tile__top,
.card-tile__foot,
.card-tile__labels {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
.card-tile__key {
  font: 500 12px var(--font-mono);
  color: rgb(var(--v-theme-on-surface-variant));
}
.card-tile__menu {
  position: relative;
  z-index: 1;
  margin-left: auto;
}
.card-tile__title {
  margin: 0;
  font-size: 14px;
  line-height: 20px;
  font-weight: 500;
  overflow-wrap: anywhere;
}
.card-tile__link {
  color: inherit;
  text-decoration: none;
}
.card-tile__link::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
}
.card-tile__link:focus-visible {
  outline: none;
}
.card-tile__link:focus-visible::after {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
.card-tile__date,
.card-tile__checklist {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.card-tile__date--error { color: rgb(var(--v-theme-error)); }
.card-tile__date--warning { color: rgb(var(--v-theme-warning)); }
.card-tile__date--success { color: rgb(var(--v-theme-success)); }
.card-tile--ghost {
  opacity: 0.4;
}
.card-tile__people {
  display: inline-flex;
  gap: 2px;
  margin-left: auto;
}
</style>
