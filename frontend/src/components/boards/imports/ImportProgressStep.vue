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

<!-- An import on its way ("92 of 176 cards", safe to leave), or one that
     stopped part-way: what happened, that the cards already imported stay,
     and Resume, which starts it again and skips what's on the board. -->
<template>
  <div class="progress-step">
    <template v-if="!stopped">
      <p class="progress-step__count">
        <span class="progress-step__big">{{ done }} of {{ plural(total, 'card') }}</span>
        <span class="progress-step__sub">comments and files follow each card</span>
      </p>
      <p class="progress-step__note">
        Safe to leave this page. A restart picks up where it stopped, and coming back here shows where it stands.
      </p>
    </template>
    <AppCallout v-else variant="error" :title="`Stopped after ${done} of ${plural(total, 'card')}`" role="alert">
      {{ error || 'The import stopped part-way.' }}
      <template v-if="imported"> The {{ plural(imported, 'card') }} already imported are on the board.</template>
      <template #actions>
        <v-btn color="primary" variant="flat" :loading="busy" :disabled="waitSeconds > 0" @click="emit('resume')">
          {{ waitSeconds > 0 ? `Resume in ${waitSeconds}s` : 'Resume' }}
        </v-btn>
      </template>
    </AppCallout>
  </div>
</template>

<script setup lang="ts">
import AppCallout from '@/components/common/AppCallout.vue'
import { plural } from '@/utils/format'

defineProps<{
  done: number
  total: number
  /** Cards the runs so far put on the board. */
  imported: number
  /** The run ended failed: offer Resume. */
  stopped: boolean
  error: string | null
  busy: boolean
  /** Seconds left before the server takes a retry (Retry-After). */
  waitSeconds: number
}>()
const emit = defineEmits<{ resume: [] }>()
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
</style>
