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

<!-- One goal: its words, where it came from, what's waiting on it, its
     history, and the buttons the caller may use. -->
<template>
  <article class="goal" :class="`goal--${goal.status}`">
    <header class="goal__head">
      <h3 class="goal__title">{{ goal.title }}</h3>
      <span v-if="goal.suggestion_basis" class="goal__badge">{{ BASIS_LABELS[goal.suggestion_basis] }}</span>
    </header>
    <p v-if="goal.measure" class="goal__measure">{{ goal.measure }}</p>
    <p class="goal__meta">
      {{ originLine(goal) }}<template v-if="goal.added_mid_period"> · added mid-period</template>
    </p>
    <p v-if="goal.why" class="goal__why">Why this: {{ goal.why }}</p>
    <p v-if="goal.status === 'proposed' && !goal.reword_note" class="goal__waiting">
      {{ goal.replaces ? 'A suggested change, waiting' : 'Waiting' }} for {{ managerName || 'the manager' }} to confirm.
    </p>
    <AppCallout v-if="goal.status === 'proposed' && goal.reword_note" variant="warning" title="Asked to reword">
      {{ goal.reword_note }}
    </AppCallout>
    <p v-if="goal.status === 'dismissed' && goal.dismiss_reason" class="goal__waiting">Not added: {{ goal.dismiss_reason }}</p>
    <details v-if="goal.history.length" class="goal__history">
      <summary>History</summary>
      <ul>
        <li v-for="(entry, i) in goal.history" :key="i">{{ historyLine(entry) }}</li>
      </ul>
    </details>
    <div v-if="hasActions" class="goal__actions">
      <v-btn v-if="goal.actions.accept" size="small" color="primary" @click="emit('accept')">
        {{ goal.status === 'suggested' ? 'Use this goal' : 'Confirm' }}
      </v-btn>
      <v-btn v-if="goal.actions.ask_reword" size="small" variant="outlined" @click="emit('reword')">Ask to reword</v-btn>
      <v-btn v-if="goal.actions.edit" size="small" variant="outlined" @click="emit('edit')">Edit</v-btn>
      <v-btn v-if="goal.actions.suggest_change" size="small" variant="outlined" @click="emit('suggest-change')">Suggest a change</v-btn>
      <v-btn v-if="goal.actions.dismiss" size="small" variant="text" @click="emit('dismiss')">
        {{ dismissLabel }}
      </v-btn>
      <v-btn v-if="goal.actions.remove" size="small" variant="text" color="error" @click="emit('remove')">Remove</v-btn>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import type { Goal } from '@/types/appraisalGoals'
import { BASIS_LABELS, historyLine, originLine } from '@/utils/appraisalGoals'

const props = defineProps<{ goal: Goal; managerName: string | null; asEmployee: boolean }>()
const emit = defineEmits<{
  accept: []
  reword: []
  edit: []
  'suggest-change': []
  dismiss: []
  remove: []
}>()

const hasActions = computed(() => Object.values(props.goal.actions).some(Boolean))
const dismissLabel = computed(() => {
  if (props.goal.status === 'suggested') return 'Dismiss'
  return props.asEmployee ? 'Withdraw' : 'Not this period'
})
</script>

<style scoped>
.goal {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.goal--dismissed {
  opacity: 0.7;
}
.goal__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.goal__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.goal__badge {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(var(--v-theme-primary), 0.12);
  color: rgb(var(--v-theme-primary));
}
.goal__measure,
.goal__meta,
.goal__why,
.goal__waiting {
  margin: 0;
  font-size: 13px;
}
.goal__meta,
.goal__waiting,
.goal__history {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.goal__history {
  font-size: 13px;
}
.goal__history ul {
  margin: 4px 0 0;
  padding-left: 18px;
}
.goal__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
}
</style>
