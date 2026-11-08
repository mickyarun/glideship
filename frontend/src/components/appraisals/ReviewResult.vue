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

<!-- The shared result: the final band and goal results, every change the
     manager made with its reason, and the reply to acknowledge it. -->
<template>
  <section class="result" aria-labelledby="result-title">
    <h2 id="result-title" class="result__title">Final band: {{ bandText(score?.final_band ?? null) }}</h2>
    <p v-if="bandChanged" class="result__change">
      Changed from {{ bandText(review.self_score?.band ?? null) }}: {{ score?.reason }}
    </p>
    <ul class="result__goals">
      <li v-for="goal in review.goals" :key="goal.id">
        <strong>{{ goal.title }}</strong> · {{ resultLabel(goal.result) }}
        <template v-if="goal.manager_reason"> (you said {{ resultLabel(goal.self_result) }}; {{ goal.manager_reason }})</template>
      </li>
    </ul>
    <template v-if="review.can.acknowledge">
      <v-textarea v-model="reply" label="Your reply (optional; HR reads it too)" rows="2" auto-grow maxlength="1000" />
      <div class="result__actions">
        <v-btn color="primary" :loading="busy" @click="emit('acknowledge', reply.trim())">Acknowledge</v-btn>
      </div>
    </template>
    <p v-else-if="review.acknowledged_at" class="result__change">
      Acknowledged<template v-if="review.reply">: “{{ review.reply }}”</template>
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { AppraisalRead } from '@/types/appraisalReview'
import { bandLabel } from '@/utils/appraisalBands'
import { resultLabel } from '@/utils/appraisalGoals'

const props = defineProps<{ review: AppraisalRead; busy: boolean }>()
const emit = defineEmits<{ acknowledge: [reply: string] }>()
const reply = ref('')
const score = computed(() => props.review.manager_score)
const bandChanged = computed(() => Boolean(score.value?.reason))

function bandText(band: number | null): string {
  return band ? `${bandLabel(band)} (${band})` : 'not scored'
}
</script>

<style scoped>
.result {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 880px;
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.result__title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}
.result__change {
  margin: 0;
  font-size: 14px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.result__goals {
  margin: 0;
  padding-left: 20px;
  font-size: 14px;
}
.result__actions {
  display: flex;
  justify-content: flex-end;
}
</style>
