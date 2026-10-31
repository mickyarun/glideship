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

<!-- The Delivery board's AI switch, at the top of its settings, in the
     same shape as a team board's AI section: the switch beside its title
     and what it does. Saved as it's flipped. Anyone without
     org:edit_settings sees it read-only. -->
<template>
  <AppPanel title="AI on the Delivery board" :note="DELIVERY_AI_NOTE" class="delivery-ai">
    <template #action>
      <v-progress-circular v-if="ai.loading.value" indeterminate size="18" width="2" aria-label="Loading" />
      <v-switch
        v-else-if="ai.settings.value"
        :model-value="ai.enabled.value"
        :label="ai.enabled.value ? 'On' : 'Off'"
        :disabled="!ai.canEdit.value || ai.saving.value"
        :loading="ai.saving.value"
        color="primary"
        density="compact"
        hide-details
        inset
        aria-label="AI on the Delivery board"
        @update:model-value="on => ai.setEnabled(!!on)"
      />
    </template>
    <AppCallout v-if="ai.error.value" variant="error" role="alert">
      {{ ai.error.value }}
      <template v-if="!ai.settings.value" #actions>
        <v-btn variant="outlined" size="small" @click="ai.load()">Try again</v-btn>
      </template>
    </AppCallout>
    <AppCallout v-else-if="ai.settings.value && !ai.settings.value.ai_enabled" variant="info" role="note">
      AI is off: no BUD stage agent starts until it's switched back on.
    </AppCallout>
    <p v-if="ai.settings.value && !ai.canEdit.value" class="delivery-ai__readonly">{{ DELIVERY_AI_READONLY }}</p>
  </AppPanel>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { useDeliveryAi } from '@/composables/useDeliveryAi'
import { DELIVERY_AI_NOTE, DELIVERY_AI_READONLY } from '@/constants/boardAgents'

const ai = useDeliveryAi()

onMounted(() => void ai.load())
</script>

<style scoped>
.delivery-ai {
  margin-bottom: 24px;
}
.delivery-ai__readonly {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
