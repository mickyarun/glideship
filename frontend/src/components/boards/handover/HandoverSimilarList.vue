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

<!-- Open BUDs that look like the draft, closest first, in a warning
     callout, each with "Link this instead" (when I may link) so the card
     joins that BUD rather than making a second one. -->
<template>
  <AppCallout variant="warning" title="Check these first: they look similar" role="note">
    <ul class="handover-similar__list">
      <li v-for="bud in similar" :key="bud.bud_id" class="handover-similar__row">
        <span class="handover-similar__key">{{ bud.key }}</span>
        <span class="handover-similar__title">{{ bud.title }}</span>
        <span class="handover-similar__meta">{{ statusLabel(bud.status) }} · {{ closeness(bud.distance) }}</span>
        <v-btn
          v-if="canLink"
          variant="outlined"
          size="small"
          :aria-label="`Link ${bud.key} instead`"
          @click="emit('link', bud.bud_id)"
        >
          Link this instead
        </v-btn>
      </li>
    </ul>
  </AppCallout>
</template>

<script setup lang="ts">
import AppCallout from '@/components/common/AppCallout.vue'
import type { SimilarBUD } from '@/types/boards'
import { statusLabel } from '@/utils/handoverChips'

const props = defineProps<{
  similar: SimilarBUD[]
  canLink: boolean
  /** Below this distance a match reads as close. */
  closeBelow: number
}>()
const emit = defineEmits<{ link: [budId: string] }>()

function closeness(distance: number): string {
  return distance < props.closeBelow ? 'close match' : 'possible match'
}
</script>

<style scoped>
.handover-similar__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}
.handover-similar__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgb(var(--v-theme-rule));
  background: rgb(var(--v-theme-surface));
}
.handover-similar__key {
  font: 500 12px var(--font-mono);
  color: rgb(var(--v-theme-on-surface-variant));
}
.handover-similar__title {
  flex: 1 1 200px;
  min-width: 0;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface));
}
.handover-similar__meta {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
