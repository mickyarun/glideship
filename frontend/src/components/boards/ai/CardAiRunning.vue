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

<!-- A stage agent working on the card: queued, or drafting with the time
     it has taken and the job's own progress line when it sends one. The
     run's status itself comes from the board's live channel; following the
     job here adds its words and covers a missed update (its end reloads
     the panel). Nothing it writes overwrites the card: it waits for review. -->
<template>
  <div class="ai-running">
    <span class="ai-running__dot" aria-hidden="true" />
    <div class="ai-running__text">
      <span class="ai-running__title">
        <span role="status">{{ title }}</span>
        <span v-if="run.status !== 'pending'"> · {{ elapsed(run.started_at ?? run.created_at) }}</span>
      </span>
      <span class="ai-running__note">{{ jobLine || NOTE }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, watch } from 'vue'
import { useJobSocket } from '@/composables/useJobSocket'
import { useNow } from '@/composables/useNow'
import { RUN_ELAPSED_TICK_MS } from '@/constants/boardAgents'
import type { AgentRunRead } from '@/types/boards'
import { logFailure } from '@/utils/logFailure'

const NOTE = "You can keep working on the card. The draft won't overwrite anything; it waits for review."
const SECONDS_PER_MINUTE = 60

const props = defineProps<{ run: AgentRunRead; skillName: string }>()
const emit = defineEmits<{ ended: [] }>()

const now = useNow(RUN_ELAPSED_TICK_MS)
const job = useJobSocket()

function elapsed(from: string): string {
  const seconds = Math.max(0, Math.floor((now.value.getTime() - Date.parse(from)) / 1000))
  const minutes = Math.floor(seconds / SECONDS_PER_MINUTE)
  return minutes ? `${minutes}m ${seconds % SECONDS_PER_MINUTE}s` : `${seconds}s`
}

// The announced words stay put; the ticking time sits beside them, outside the live region.
const title = computed(() => `${props.skillName} ${props.run.status === 'pending' ? 'is queued' : 'is drafting'}`)
const jobLine = computed(() => (job.isActive.value ? job.status.value?.statusMessage ?? '' : ''))

watch(() => props.run.job_id, id => {
  job.stopTracking()
  if (!id) return
  job.startTracking(id, {
    onComplete: () => emit('ended'),
    onError: error => {
      logFailure('boards', 'agent job', error)
      emit('ended')
    },
    onMissing: () => emit('ended'),
  })
}, { immediate: true })
onUnmounted(() => job.stopTracking())
</script>

<style scoped>
.ai-running {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(var(--v-theme-info), 0.08);
  border-left: 3px solid rgb(var(--v-theme-info));
}
.ai-running__dot {
  flex: none;
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  background: rgb(var(--v-theme-info));
  animation: ai-pulse 1.4s ease-in-out infinite;
}
.ai-running__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.ai-running__title {
  font-size: 13px;
  font-weight: 600;
}
.ai-running__note {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
@keyframes ai-pulse {
  50% {
    opacity: 0.35;
  }
}
@media (prefers-reduced-motion: reduce) {
  .ai-running__dot {
    animation: none;
  }
}
</style>
