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

<!-- Cancel run, beside a queued or drafting run (editors). A queued run
     cancels at once; a drafting one asks first, since the work so far is
     thrown away. A refusal shows under the button. -->
<template>
  <div class="ai-cancel">
    <v-btn size="small" variant="text" :loading="canceling" @click="ask">Cancel run</v-btn>
    <span v-if="error" class="ai-cancel__error" role="alert">{{ error }}</span>
    <AppConfirmDialog
      v-model="confirming"
      :title="`Cancel ${skillName}?`"
      body="It stops drafting now and saves nothing. Nothing on the card changes."
      action="Cancel run"
      color="error"
      :busy="canceling"
      @confirm="confirm"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { useCardRunCancel } from '@/composables/useCardRunCancel'
import type { AgentRunRead } from '@/types/boards'

const props = defineProps<{ run: AgentRunRead; skillName: string }>()

const { canceling, error, cancel } = useCardRunCancel()
const confirming = ref(false)

function ask(): void {
  if (props.run.status === 'running') confirming.value = true
  else void cancel(props.run)
}

// Closes either way: a refusal reads under the button.
async function confirm(): Promise<void> {
  await cancel(props.run)
  confirming.value = false
}
</script>

<style scoped>
.ai-cancel {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  margin-left: auto;
}
.ai-cancel__error {
  font-size: 12px;
  color: rgb(var(--v-theme-error));
}
</style>
