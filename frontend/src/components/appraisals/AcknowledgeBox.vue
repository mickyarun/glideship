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

<!-- The last step on a shared result: an optional reply, then "I've read
     this". It says plainly that reading isn't agreeing. Once done, it
     shows when and the reply. -->
<template>
  <AppPanel v-if="review.can.acknowledge" title="Done reading?">
    <v-textarea
      v-model="reply"
      label="Your reply"
      :hint="`Optional · ${manager} and HR see it`"
      persistent-hint
      rows="2"
      auto-grow
      maxlength="1000"
    />
    <div class="ack__foot">
      <p class="ack__muted">This confirms you've read it. It doesn't mean you agree.</p>
      <v-btn color="primary" :loading="busy" @click="emit('acknowledge', reply.trim())">I've read this</v-btn>
    </div>
  </AppPanel>
  <p v-else-if="review.acknowledged_at" class="ack__muted">
    {{ isSelf ? 'You' : person }} read this on {{ longDate(review.acknowledged_at.slice(0, 10)) }}<template v-if="review.reply">, replying: “{{ review.reply }}”</template>
  </p>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { AppraisalRead } from '@/types/appraisalReview'
import { firstName } from '@/utils/appraisalReview'
import { longDate } from '@/utils/appraisalSetup'

const props = defineProps<{ review: AppraisalRead; busy: boolean; isSelf: boolean }>()
const emit = defineEmits<{ acknowledge: [reply: string] }>()
const reply = ref('')
const manager = computed(() => firstName(props.review.manager_name, 'Your manager'))
const person = computed(() => firstName(props.review.person_name, 'They'))
</script>

<style scoped>
.ack__foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
}
.ack__muted {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
