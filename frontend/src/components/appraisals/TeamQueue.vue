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

<!-- The manager's one to-do queue, oldest first, each with one button. A
     note still waiting on its check-in shows, quietly, at the end. -->
<template>
  <AppPanel :title="`To do · ${count}`" note="Oldest first. Each takes a few minutes." flush>
    <p v-if="!items.length" class="queue__empty">Nothing waiting on you.</p>
    <ul class="queue">
      <li v-for="item in items" :key="item.kind + item.target_id" class="queue__item" :class="{ 'queue__item--quiet': !actionable(item) }">
        <span class="queue__avatar" aria-hidden="true">{{ initials(item.person_name ?? '') }}</span>
        <div class="queue__words">
          <span class="queue__title">{{ todoTitle(item) }}</span>
          <span class="queue__detail">{{ detail(item) }}</span>
        </div>
        <span v-if="item.late" class="queue__late">{{ dueLine(item.due_on, today) }}</span>
        <v-btn v-if="actionable(item)" size="small" variant="outlined" :to="todoRoute(item)">{{ todoAction(item) }}</v-btn>
      </li>
    </ul>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { TodoItem } from '@/types/appraisalTodo'
import { longDate } from '@/utils/appraisalSetup'
import { initials } from '@/utils/appraisalTeamView'
import { actionable, todoRoute } from '@/utils/appraisalTodo'
import { dueLine, todayIso, todoAction, todoTitle } from '@/utils/appraisalTodoWords'

/** ``noteDays``: the cycle's working days for a note once its check-in is sent. */
const props = defineProps<{ items: TodoItem[]; noteDays: number }>()
const today = todayIso()
const count = computed(() => props.items.filter(actionable).length)

function detail(item: TodoItem): string {
  const due = item.due_on ? `Due ${longDate(item.due_on)}.` : ''
  switch (item.kind) {
    case 'note':
      return `They sent their check-in. Your notes: ${due}`
    case 'waiting_on_check_in':
      return `Not sent yet. Your notes are due ${props.noteDays} working day${props.noteDays === 1 ? '' : 's'} after it is.`
    case 'set_goals':
      return `Your org asks for at least ${item.count} more. ${due}`.trim()
    case 'confirm_goals':
      return `${due} Goals lock when HR opens reviews.`.trim()
    default:
      return due
  }
}
</script>

<style scoped>
.queue {
  margin: 0;
  padding: 0;
  list-style: none;
}
.queue__empty {
  margin: 0;
  padding: 0 20px 18px;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.queue__item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 12px 20px;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.queue__item--quiet {
  opacity: 0.75;
}
.queue__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 600;
  background: var(--color-accent-soft);
  color: var(--color-accent-text);
}
.queue__words {
  display: flex;
  flex: 1 1 240px;
  flex-direction: column;
  min-width: 0;
}
.queue__title {
  font-size: 14px;
  font-weight: 600;
}
.queue__detail {
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.queue__late {
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--v-theme-error));
}
</style>
