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

<!-- A board tile's last row: the due date, the checklist's progress and
     the assignees. Editors change the date and the assignees right here
     (both sit above the tile's stretched link); nothing shows when the
     card has none of them and can't be edited. -->
<template>
  <div v-if="canEdit || date || card.checklist_total || card.assignee_ids.length" class="tile-foot">
    <CardDuePicker :card="card" :now="now" :can-edit="canEdit" @failed="emit('failed', $event)" />
    <span
      v-if="card.checklist_total"
      class="tile-foot__checklist"
      :aria-label="`Checklist ${card.checklist_done} of ${card.checklist_total} done`"
    >
      <v-icon icon="mdi-checkbox-marked-outline" size="14" aria-hidden="true" />
      {{ card.checklist_done }}/{{ card.checklist_total }}
    </span>
    <span class="tile-foot__people">
      <CardAssigneePicker :card="card" :can-edit="canEdit" @failed="emit('failed', $event)" />
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import CardAssigneePicker from '@/components/boards/board/CardAssigneePicker.vue'
import CardDuePicker from '@/components/boards/board/CardDuePicker.vue'
import type { CardSummary } from '@/types/boards'
import { dateChip } from '@/utils/cardChips'

const props = defineProps<{ card: CardSummary; now: Date; canEdit: boolean }>()
const emit = defineEmits<{ failed: [error: string] }>()

const date = computed(() => dateChip(props.card, props.now))
</script>

<style scoped>
.tile-foot {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
.tile-foot__checklist {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.tile-foot__people {
  margin-left: auto;
}
</style>
