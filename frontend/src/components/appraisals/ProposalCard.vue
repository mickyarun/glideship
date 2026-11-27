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

<!-- One goal the person suggested, for the manager to decide on: what it
     is, how we'll know, their reason, and Confirm, Suggest a change or
     Reject. -->
<template>
  <article class="proposal">
    <header class="proposal__head">
      <h3 class="proposal__title">{{ goal.title }}</h3>
      <span class="proposal__muted">Suggested {{ shortDay(goal.created_at) }}</span>
    </header>
    <p v-if="goal.measure" class="proposal__line">How we'll know: {{ goal.measure }}</p>
    <template v-if="reason">
      <span class="proposal__label">{{ who }}'s reason</span>
      <p class="proposal__line">“{{ reason }}”</p>
    </template>
    <div class="proposal__actions">
      <v-btn size="small" color="primary" :disabled="full && !goal.replaces" @click="emit('accept')">Confirm</v-btn>
      <v-btn size="small" variant="outlined" @click="emit('reword')">Suggest a change</v-btn>
      <v-btn size="small" variant="outlined" color="error" @click="emit('decline')">Reject</v-btn>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Goal } from '@/types/appraisalGoals'
import { proposalReason } from '@/utils/appraisalGoals'

const props = defineProps<{ goal: Goal; who: string; full: boolean }>()
const emit = defineEmits<{ accept: []; reword: []; decline: [] }>()
const reason = computed(() => proposalReason(props.goal))

function shortDay(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}
</script>

<style scoped>
.proposal {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 0;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.proposal__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.proposal__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.proposal__label {
  font-size: 12px;
  font-weight: 600;
}
.proposal__line {
  margin: 0;
  font-size: 14px;
}
.proposal__muted {
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.proposal__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
}
</style>
