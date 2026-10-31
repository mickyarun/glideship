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

<!-- The card's last run, when it failed or was canceled: what happened in
     the run's own words, that the card didn't change, and Retry (the same
     call as Run) for editors while the agent is still on the stage. -->
<template>
  <AppCallout
    :variant="run.status === 'failed' ? 'error' : 'info'"
    :role="run.status === 'failed' ? 'alert' : 'status'"
    :title="title"
  >
    {{ run.error_message || FALLBACK }} Nothing on the card changed.
    <template v-if="canRetry" #actions>
      <v-btn variant="outlined" size="small" :disabled="busy" @click="emit('retry')">Try again</v-btn>
    </template>
  </AppCallout>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import { RUN_ENDED_TITLES } from '@/constants/boardAgents'
import type { AgentRunRead } from '@/types/boards'

const FALLBACK = "The run stopped before it wrote a draft."

const props = defineProps<{ run: AgentRunRead; skillName: string; canRetry: boolean; busy: boolean }>()
const emit = defineEmits<{ retry: [] }>()

const title = computed(() => RUN_ENDED_TITLES[props.run.status]?.(props.skillName) ?? props.skillName)
</script>
