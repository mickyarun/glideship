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

<!-- Adding one goal in place: what it is, how we'll know, and (for a
     manager) why this, why now, which the person reads. -->
<template>
  <form class="add-goal" @submit.prevent="submit">
    <h3 class="add-goal__title">{{ heading }}</h3>
    <v-text-field v-model="title" label="Goal" maxlength="200" hide-details="auto" />
    <v-text-field v-model="measure" label="How we'll know" maxlength="300" hide-details="auto" />
    <v-textarea v-if="needsReason" v-model="reason" :label="`Why this, why now (${who} reads this)`" rows="2" auto-grow maxlength="300" hide-details="auto" />
    <div class="add-goal__foot">
      <v-btn type="submit" variant="outlined" :disabled="!ready" :loading="busy">Add goal</v-btn>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { GoalBody } from '@/types/appraisalGoals'

const props = defineProps<{ heading: string; who: string; needsReason: boolean; busy: boolean }>()
const emit = defineEmits<{ submit: [body: GoalBody] }>()
const title = ref('')
const measure = ref('')
const reason = ref('')
const ready = computed(() => Boolean(title.value.trim()) && (!props.needsReason || Boolean(reason.value.trim())))

function submit(): void {
  if (!ready.value) return
  emit('submit', { title: title.value.trim(), measure: measure.value.trim(), reason: reason.value.trim() })
}

/** Clear the form once the goal is in. */
function reset(): void {
  title.value = ''
  measure.value = ''
  reason.value = ''
}

defineExpose({ reset })
</script>

<style scoped>
.add-goal {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.add-goal__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}
.add-goal__foot {
  display: flex;
  justify-content: flex-end;
}
</style>
