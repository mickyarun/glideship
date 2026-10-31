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
     same card shape as the sections below it (icon, title, what it does)
     with the switch beside the title. Saved as it's flipped, and it says
     so. Anyone without org:edit_settings sees it read-only. -->
<template>
  <v-card class="pa-6 mb-6 delivery-ai" color="surface" border>
    <div class="d-flex align-center ga-3">
      <v-avatar size="36" color="surface-variant" rounded="lg">
        <v-icon :icon="AI_ICON" size="22" />
      </v-avatar>
      <div class="delivery-ai__head">
        <h2 class="text-body-1 font-weight-medium delivery-ai__title">AI on the Delivery board</h2>
        <div class="text-caption text-medium-emphasis">{{ DELIVERY_AI_NOTE }}</div>
      </div>
      <v-progress-circular v-if="ai.loading.value" indeterminate size="18" width="2" aria-label="Loading" />
      <v-switch
        v-else-if="ai.settings.value"
        :model-value="ai.enabled.value"
        :label="ai.enabled.value ? 'On' : 'Off'"
        :disabled="!ai.canEdit.value || ai.saving.value"
        :loading="ai.saving.value"
        class="delivery-ai__switch"
        color="primary"
        density="compact"
        hide-details
        inset
        aria-label="AI on the Delivery board"
        @update:model-value="on => ai.setEnabled(!!on)"
      />
    </div>
    <p v-if="ai.settings.value && ai.canEdit.value" class="delivery-ai__note">{{ DELIVERY_AI_SAVES }}</p>
    <AppCallout v-if="ai.error.value" variant="error" role="alert" class="mt-4">
      {{ ai.error.value }}
      <template v-if="!ai.settings.value" #actions>
        <v-btn variant="outlined" size="small" @click="ai.load()">Try again</v-btn>
      </template>
    </AppCallout>
    <AppCallout v-else-if="ai.settings.value && !ai.settings.value.ai_enabled" variant="info" role="note" class="mt-4">
      AI is off: no BUD stage agent starts until it's switched back on.
    </AppCallout>
    <p v-if="ai.settings.value && !ai.canEdit.value" class="delivery-ai__note">{{ DELIVERY_AI_READONLY }}</p>
  </v-card>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import { useDeliveryAi } from '@/composables/useDeliveryAi'
import { AI_ICON, DELIVERY_AI_NOTE, DELIVERY_AI_READONLY, DELIVERY_AI_SAVES } from '@/constants/boardAgents'

const ai = useDeliveryAi()

onMounted(() => void ai.load())
</script>

<style scoped>
.delivery-ai__head {
  flex: 1 1 auto;
  min-width: 0;
}
.delivery-ai__title {
  margin: 0;
}
.delivery-ai__switch {
  flex: none;
}
.delivery-ai__note {
  margin: 12px 0 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
