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

<!-- An import I left open, offered when the wizard opens without one:
     continue it where it stands, or discard it and start fresh. -->
<template>
  <AppCallout v-if="offer" variant="info" role="status" :title="`Continue your import from ${formatDateTime(offer.created_at)}?`">
    {{ what }}
    <span v-if="open.error.value" class="open-offer__error" role="alert">{{ open.error.value }}</span>
    <template #actions>
      <v-btn color="primary" variant="flat" size="small" :disabled="open.discarding.value" @click="emit('continue')">Continue</v-btn>
      <v-btn variant="outlined" size="small" :loading="open.discarding.value" @click="open.discard()">Discard</v-btn>
    </template>
  </AppCallout>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import type { OpenImports } from '@/composables/useOpenImports'
import { formatDateTime } from '@/utils/date'

const props = defineProps<{ open: OpenImports }>()
const emit = defineEmits<{ continue: [] }>()

const offer = computed(() => props.open.offer.value)
const what = computed(() => {
  const s = offer.value
  if (!s) return ''
  if (s.status === 'running') return `It's importing: ${s.processed_count} of ${s.total_cards ?? 0} cards so far.`
  if (s.status === 'ready') return "The board is read and waiting for your review."
  return 'The board is still being read.'
})
</script>

<style scoped>
.open-offer__error {
  display: block;
  margin-top: 6px;
  color: rgb(var(--v-theme-error));
}
</style>
