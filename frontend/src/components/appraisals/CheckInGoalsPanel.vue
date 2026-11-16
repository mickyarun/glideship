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

<!-- The period's goals, at the top of every check-in, so nothing further
     down refers to a goal the person hasn't just seen. Goals with a number
     in their measure get a box for this month's value and its source. -->
<template>
  <section class="goals" aria-labelledby="checkin-goals">
    <h2 id="checkin-goals" class="goals__title">{{ periodLabel }} goals</h2>
    <p v-if="!goals.length" class="goals__empty">
      No goals agreed for this period yet. Your work below still counts under its heading.
    </p>
    <ol v-else class="goals__list">
      <li v-for="goal in goals" :key="goal.id" class="goals__item">
        <p class="goals__goal"><span class="goals__num">{{ goal.position }}</span>{{ goal.title }}</p>
        <p v-if="goal.measure" class="goals__measure">How you'll know: {{ goal.measure }}</p>
        <div v-if="editable" class="goals__value">
          <v-text-field
            v-model="drafts[goal.id].value"
            label="This month's value"
            density="compact"
            hide-details
            maxlength="100"
          />
          <v-text-field
            v-model="drafts[goal.id].source_note"
            label="Where it came from"
            density="compact"
            hide-details
            maxlength="200"
          />
          <v-btn
            variant="outlined"
            size="small"
            :disabled="!drafts[goal.id].value.trim()"
            @click="save(goal.id)"
          >
            Save value
          </v-btn>
        </div>
        <p v-else-if="goal.value" class="goals__reported">
          {{ goal.value }}<span v-if="goal.source_note"> · {{ goal.source_note }}</span>
          <span class="goals__by"> · reported by the employee</span>
        </p>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { CheckInGoal, GoalValueIn } from '@/types/appraisal'

const props = defineProps<{ goals: CheckInGoal[]; editable: boolean; periodLabel: string }>()
const emit = defineEmits<{ save: [goalId: string, body: GoalValueIn] }>()

const drafts = reactive<Record<string, { value: string; source_note: string }>>({})

watch(
  () => props.goals,
  goals => {
    for (const goal of goals) {
      drafts[goal.id] = { value: goal.value ?? '', source_note: goal.source_note ?? '' }
    }
  },
  { immediate: true },
)

function save(goalId: string): void {
  const draft = drafts[goalId]
  emit('save', goalId, { value: draft.value.trim(), source_note: draft.source_note.trim(), source_url: null })
}
</script>

<style scoped>
.goals {
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.goals__title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
}
.goals__empty,
.goals__measure,
.goals__reported {
  margin: 4px 0 0;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.goals__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.goals__goal {
  margin: 0;
  font-weight: 600;
}
.goals__num {
  display: inline-block;
  min-width: 20px;
  margin-right: 6px;
  color: rgb(var(--v-theme-primary));
}
.goals__value {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr) auto;
  gap: 8px;
  align-items: center;
  margin-top: 8px;
}
.goals__by {
  font-style: italic;
}
@media (max-width: 600px) {
  .goals__value {
    grid-template-columns: 1fr;
  }
}
</style>
