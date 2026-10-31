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

<!-- The card's last run, when it failed or was canceled: what happened
     in product words for its error code, a link to the AI settings for
     whoever can connect the AI service when it isn't, and Retry (the same
     call as Run) for editors while the agent is still on the stage. The
     raw reason goes to the console; board admins (the only ones the server
     sends it to) can also open it under the words, in Details. -->
<template>
  <AppCallout
    :variant="run.status === 'failed' ? 'error' : 'info'"
    :role="run.status === 'failed' ? 'alert' : 'status'"
    :title="title"
  >
    {{ words }}
    <router-link v-if="settingsLink" :to="settingsLink" class="ai-ended__link">Open AI settings</router-link>
    <details v-if="details" class="ai-ended__details">
      <summary class="ai-ended__summary">Details</summary>
      <pre class="ai-ended__raw">{{ details }}</pre>
    </details>
    <template v-if="canRetry" #actions>
      <v-btn variant="outlined" size="small" :disabled="busy" @click="emit('retry')">Try again</v-btn>
    </template>
  </AppCallout>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import { usePermissions } from '@/composables/usePermissions'
import { RUN_ENDED_TITLES, runEndedCode, runEndedWords } from '@/constants/agentRunEnded'
import type { AgentRunRead } from '@/types/boards'
import { logFailure } from '@/utils/logFailure'

/** Where the organization's AI service is connected, and who may connect it. */
const AI_SETTINGS = { name: 'settings' }
const AI_SETTINGS_PERMISSION = 'integrations:configure'

const props = defineProps<{
  run: AgentRunRead
  skillName: string
  canRetry: boolean
  busy: boolean
  /** Board admins may read the run's raw reason. */
  canSeeDetails: boolean
}>()
const emit = defineEmits<{ retry: [] }>()

const { hasPermission } = usePermissions()
const title = computed(() => RUN_ENDED_TITLES[props.run.status]?.(props.skillName) ?? props.skillName)
const words = computed(() => runEndedWords(props.run))
const details = computed(() => (props.canSeeDetails ? props.run.error_message?.trim() || null : null))
const settingsLink = computed(() =>
  runEndedCode(props.run) === 'AI_NOT_CONFIGURED' && hasPermission(AI_SETTINGS_PERMISSION) ? AI_SETTINGS : null,
)

// The raw reason is for whoever debugs it, once per run.
watch(() => props.run.id, () => {
  if (props.run.error_message) logFailure('boards', `agent run ${props.run.id}`, props.run.error_message)
}, { immediate: true })
</script>

<style scoped>
.ai-ended__link {
  margin-left: 4px;
  color: var(--color-accent-text);
}
.ai-ended__details {
  margin-top: 6px;
  font-size: 12px;
}
.ai-ended__summary {
  cursor: pointer;
  color: rgb(var(--v-theme-on-surface-variant));
}
.ai-ended__raw {
  margin: 4px 0 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: var(--font-mono);
  font-size: 12px;
}
</style>
