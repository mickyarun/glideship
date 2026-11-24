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

<!-- One dot per check-in period: filled when sent, a ring when late, a
     cross when missed, empty when not open or not sent yet. -->
<template>
  <span class="dots" role="img" :aria-label="label">
    <span v-for="(state, i) in states" :key="i" class="dots__dot" :class="`dots__dot--${state}`" />
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MonthStateName } from '@/types/appraisalTeam'

const WORDS: Record<MonthStateName, string> = { sent: 'sent', late: 'late', open: 'not sent yet', missed: 'missed', not_open: 'not open yet' }

const props = defineProps<{ states: MonthStateName[]; months: string[] }>()
const label = computed(() => props.states.map((s, i) => `${props.months[i] ?? ''} ${WORDS[s]}`).join(', '))
</script>

<style scoped>
.dots {
  display: inline-flex;
  gap: 6px;
}
.dots__dot {
  width: 10px;
  height: 10px;
  border-radius: var(--radius-pill);
  border: 1.5px solid rgb(var(--v-theme-rule));
}
.dots__dot--sent {
  background: rgb(var(--v-theme-primary));
  border-color: rgb(var(--v-theme-primary));
}
.dots__dot--late {
  border-color: rgb(var(--v-theme-error));
}
.dots__dot--missed {
  background: rgb(var(--v-theme-rule));
}
</style>
