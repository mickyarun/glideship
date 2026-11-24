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

<!-- The two questions only the manager answers and only HR reads: ready for
     the next level, and any concern about performance (with a note). The
     person never sees this part. -->
<template>
  <div class="hr-only">
    <div class="hr-only__q">
      <span>Ready for the next level now?</span>
      <AppPillToggle :model-value="yesNo(form.ready_next_level)" :options="YES_NO" aria-label="Ready for the next level" @update:model-value="v => (form.ready_next_level = v === 'yes')" />
    </div>
    <div class="hr-only__q">
      <span>Any concern about {{ who }}'s performance?</span>
      <AppPillToggle :model-value="yesNo(form.performance_concern)" :options="NO_YES" aria-label="Performance concern" @update:model-value="v => (form.performance_concern = v === 'yes')" />
    </div>
    <v-textarea v-if="form.performance_concern" v-model="form.concern_note" label="What concerns you" rows="2" auto-grow maxlength="500" hide-details="auto" />
  </div>
</template>

<script setup lang="ts">
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import type { ManagerBody } from '@/types/appraisalReview'

defineProps<{ who: string }>()
const form = defineModel<ManagerBody>({ required: true })

const YES_NO = [
  { label: 'Yes', value: 'yes' },
  { label: 'No', value: 'no' },
]
const NO_YES = [...YES_NO].reverse()

function yesNo(value: boolean | null): string {
  return value === null ? '' : value ? 'yes' : 'no'
}
</script>

<style scoped>
.hr-only {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.hr-only__q {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
  font-size: 14px;
}
</style>
