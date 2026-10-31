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

<!-- Where a handed-over BUD came from: the board and card (key, title,
     Open card), the card's handovers, its comments read only, and whether
     the BUD can still go back. A card on a board I can't open says only
     that; a BUD that wasn't handed over shows no panel. The data lives in
     stores/budOrigin.ts, shared with Send back. -->
<template>
  <AppPanel v-if="origin?.hidden" title="Origin">
    <p class="origin__text">Came from a board you can't see.</p>
  </AppPanel>
  <AppPanel v-else-if="card" title="Origin">
    <template #action>
      <router-link :to="cardLink" class="origin__open">Open card</router-link>
    </template>
    <div class="origin">
      <router-link :to="{ name: 'board', params: { key: card.board.key } }" class="origin__board">
        {{ card.board.name }} board
      </router-link>
      <div class="origin__card">
        <span class="origin__key">{{ card.key }}</span>
        <span class="origin__title">{{ card.title }}</span>
      </div>
      <ul v-if="others.length" class="origin__list" aria-label="Other BUDs from this card">
        <HandoverBudRow v-for="h in others" :key="h.id" :handover="h" :can-retry="false" :retrying="false" />
      </ul>
      <OriginComments
        :comments="store.comments" :has-more="!!store.nextCursor" :loading="store.loadingMore" @more="store.more()"
      />
      <p class="origin__text">{{ returnNote }}</p>
    </div>
  </AppPanel>
  <AppCallout v-else-if="store.error && store.budId === budId" variant="error">{{ store.error }}</AppCallout>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import HandoverBudRow from '@/components/boards/handover/HandoverBudRow.vue'
import OriginComments from '@/components/buds/origin/OriginComments.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { useBudOriginStore } from '@/stores/budOrigin'
import type { BUDStatus } from '@/types'
import { canSendBack } from '@/utils/handoverChips'

const props = defineProps<{ budId: string; status: BUDStatus }>()

const store = useBudOriginStore()
const origin = computed(() => (store.budId === props.budId ? store.origin : null))
const card = computed(() => origin.value?.card ?? null)
// The card's other BUDs; this one is the page itself.
const others = computed(() => (origin.value?.handovers ?? []).filter(h => h.bud_id !== props.budId))
const cardLink = computed(() =>
  card.value ? { name: 'board-card', params: { key: card.value.board.key, number: card.value.number } } : '',
)
const returnNote = computed(() => {
  if (!store.active) return 'Handed over earlier; it no longer holds this BUD.'
  return canSendBack(props.status)
    ? 'It can be sent back to the card until development starts.'
    : 'Development has started, so it stays here. Raise problems on the BUD, as a comment or a bug.'
})

// A status change (sent back, discarded, restored) can change the card's handovers.
watch([() => props.budId, () => props.status], ([id]) => void store.load(id), { immediate: true })
</script>

<style scoped>
.origin {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.origin__board,
.origin__open {
  font-size: 13px;
  color: rgb(var(--v-theme-primary));
}
.origin__card {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.origin__key {
  font: 500 12px var(--font-mono);
  color: rgb(var(--v-theme-on-surface-variant));
}
.origin__title {
  font-size: 14px;
  font-weight: 500;
  overflow-wrap: anywhere;
}
.origin__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.origin__text {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
