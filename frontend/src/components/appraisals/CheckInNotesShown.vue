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

<!-- The manager's sent notes answering a check-in: keep doing, try next. -->
<template>
  <AppPanel :title="`Notes from ${firstName(feedback.manager_name, 'your manager')}`">
    <dl class="ci-notes">
      <dt>Keep doing</dt>
      <dd>{{ feedback.keep }}</dd>
      <dt>Try next</dt>
      <dd>{{ feedback.try_next }}</dd>
    </dl>
  </AppPanel>
</template>

<script setup lang="ts">
import AppPanel from '@/components/common/AppPanel.vue'
import type { FeedbackShown } from '@/types/appraisalFeedback'
import { firstName } from '@/utils/appraisalReview'

defineProps<{ feedback: FeedbackShown }>()
</script>

<style scoped>
.ci-notes {
  margin: 0;
}
.ci-notes dt {
  font-size: 12px;
  font-weight: 600;
}
.ci-notes dd {
  margin: 0 0 8px;
  font-size: 14px;
  white-space: pre-line;
}
</style>
