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

<!-- A quiet "AI" chip on a board tile while a stage agent works on the
     card (queued or drafting), in the same small mono style as the
     repository chip. Nothing shows otherwise. -->
<template>
  <span v-if="run" class="ai-chip" :title="title" role="img" :aria-label="title">
    <v-icon :icon="AI_ICON" size="14" aria-hidden="true" />
    <span aria-hidden="true">AI</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { AI_ICON } from '@/constants/boardAgents'
import { useBoardAgentRunsStore } from '@/stores/boardAgentRuns'

const props = defineProps<{ cardId: string }>()

const runs = useBoardAgentRunsStore()
const run = computed(() => runs.runFor(props.cardId))
const title = computed(() => (run.value?.status === 'pending' ? 'AI run queued' : 'AI running'))
</script>

<style scoped>
.ai-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font: 500 12px var(--font-mono);
  color: rgb(var(--v-theme-info));
}
</style>
