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

<!-- An import on its way ("92 of 176 cards", then the bar; safe to
     leave), or one that stopped part-way: what happened (and why a retry
     was refused), that the cards already imported stay, Resume (which
     skips what's on the board), Review again when the board changed under
     it, and the board itself or a fresh start. -->
<template>
  <div class="progress-step">
    <p v-if="!stopped" class="progress-step__count">
      <span class="progress-step__big">{{ done }} of {{ plural(total, 'card') }}</span>
      <span class="progress-step__sub">comments and files follow each card</span>
    </p>
    <div
      class="progress-step__bar"
      :class="{ 'progress-step__bar--stopped': stopped }"
      role="progressbar"
      aria-label="Import progress"
      aria-valuemin="0"
      :aria-valuemax="total"
      :aria-valuenow="done"
      :aria-valuetext="`${done} of ${total}`"
    >
      <span class="progress-step__fill" :style="{ width: `${percent}%` }" />
    </div>
    <p v-if="!stopped" class="progress-step__note">
      Safe to leave this page. A restart picks up where it stopped, and coming back here shows where it stands.
    </p>
    <template v-else>
      <AppCallout variant="error" :title="`Stopped after ${done} of ${plural(total, 'card')}`" role="alert">
        {{ error || 'The import stopped part-way.' }}
        <template v-if="imported"> The {{ plural(imported, 'card') }} already imported are on the board.</template>
        <span v-if="failure" class="progress-step__failure">{{ failure }}</span>
        <template #actions>
          <v-btn v-if="canReview" color="primary" variant="flat" :loading="busy" @click="emit('review')">Review again</v-btn>
          <v-btn
            :color="canReview ? undefined : 'primary'"
            :variant="canReview ? 'outlined' : 'flat'"
            :loading="busy && !canReview"
            :disabled="waitSeconds > 0"
            @click="emit('resume')"
          >
            {{ waitSeconds > 0 ? `Resume in ${waitSeconds}s` : 'Resume' }}
          </v-btn>
        </template>
      </AppCallout>
      <div class="progress-step__more">
        <v-btn v-if="boardKey" variant="outlined" :to="{ name: 'board', params: { key: boardKey } }">Open the board</v-btn>
        <v-btn variant="text" :disabled="busy" @click="emit('start-over')">Start over</v-btn>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import { plural } from '@/utils/format'

const props = defineProps<{
  done: number
  total: number
  /** Cards the runs so far put on the board. */
  imported: number
  /** The run ended failed: offer Resume. */
  stopped: boolean
  error: string | null
  /** Why the last retry was refused, if it was. */
  failure: string | null
  busy: boolean
  /** Seconds left before the server takes a retry (Retry-After). */
  waitSeconds: number
  /** The board the cards went into, once it exists. */
  boardKey: string | null
  /** Resume can't work as mapped (a stage is gone): offer the review again. */
  canReview: boolean
}>()
const emit = defineEmits<{ resume: []; review: []; 'start-over': [] }>()

const percent = computed(() => (props.total > 0 ? Math.min(100, Math.round((props.done * 100) / props.total)) : 0))
</script>

<style scoped>
.progress-step {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.progress-step__count {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 10px;
  margin: 0;
}
.progress-step__big {
  font-size: 22px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.progress-step__sub,
.progress-step__note {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.progress-step__bar {
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.08);
}
.progress-step__fill {
  display: block;
  height: 100%;
  background: rgb(var(--v-theme-primary));
  transition: width 0.3s ease;
}
.progress-step__bar--stopped .progress-step__fill {
  background: rgb(var(--v-theme-error));
}
@media (prefers-reduced-motion: reduce) {
  .progress-step__fill {
    transition: none;
  }
}
.progress-step__failure {
  display: block;
  margin-top: 6px;
}
.progress-step__more {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
</style>
