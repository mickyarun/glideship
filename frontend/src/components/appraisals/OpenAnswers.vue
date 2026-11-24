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

<!-- The two open answers from the person's review, read-only: what they're
     most proud of and what they'd do differently. Nothing shows when both
     were left empty. -->
<template>
  <dl v-if="score && (score.proud || score.differently)" class="answers">
    <div v-if="score.proud" class="answers__item">
      <dt>Most proud of</dt>
      <dd>“{{ score.proud }}”</dd>
    </div>
    <div v-if="score.differently" class="answers__item">
      <dt>Would do differently</dt>
      <dd>“{{ score.differently }}”</dd>
    </div>
  </dl>
  <p v-else class="answers__none">{{ who }} left these open.</p>
</template>

<script setup lang="ts">
import type { SelfScore } from '@/types/appraisalReview'

defineProps<{ score: SelfScore | null; who: string }>()
</script>

<style scoped>
.answers {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
}
.answers__item dt {
  font-size: 13px;
  font-weight: 600;
}
.answers__item dd {
  margin: 2px 0 0;
  font-size: 14px;
  white-space: pre-line;
}
.answers__none {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
