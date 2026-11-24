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

<!-- One free-text question of the check-in: a box to write in, or the
     words read-only for anyone else. -->
<template>
  <FormStep :number="number" :title="title" :hint="hint">
    <v-textarea v-if="editable" v-model="text" :label="label" rows="2" auto-grow :maxlength="1000" hide-details="auto" />
    <p v-else class="ci-text">{{ text ? `“${text}”` : 'Nothing written.' }}</p>
  </FormStep>
</template>

<script setup lang="ts">
import FormStep from '@/components/appraisals/FormStep.vue'

defineProps<{ number: number; title: string; hint: string; label: string; editable: boolean }>()
const text = defineModel<string>({ required: true })
</script>

<style scoped>
.ci-text {
  margin: 0;
  font-size: 14px;
  white-space: pre-line;
}
</style>
