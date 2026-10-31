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

<!-- The BUDs a card on the board was handed over to, kept quiet: each live
     one's key with a status dot (up to a few), or the "2 of 3 in prod"
     roll-up when there are more; "Delivered" once every one is in prod.
     Text only: the card's own link covers the tile. -->
<template>
  <span v-if="chips.length" class="bud-chips">
    <span class="d-sr-only">{{ summary }}</span>
    <span v-if="card.delivery === 'delivered'" class="bud-chips__done" aria-hidden="true">
      <v-icon icon="mdi-check-all" size="14" />{{ chips.length > 1 ? deliveryRollup(card.handovers) : 'Delivered' }}
    </span>
    <span v-else-if="chips.length > max" class="bud-chips__chip" aria-hidden="true">{{ deliveryRollup(card.handovers) }}</span>
    <template v-else>
      <span v-for="chip in chips" :key="chip.bud_id" class="bud-chips__chip" aria-hidden="true">
        <span class="bud-chips__dot" :style="{ background: `rgb(var(--v-theme-${statusColor(chip.status)}))` }" />
        {{ chip.bud_key }}
      </span>
    </template>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { BUD_CHIPS_SHOWN } from '@/constants/boards'
import type { CardSummary } from '@/types/boards'
import { chipLabel, deliveryRollup, statusColor } from '@/utils/handoverChips'

const props = defineProps<{ card: CardSummary }>()
const max = BUD_CHIPS_SHOWN

const chips = computed(() => (props.card.handovers ?? []).filter(c => c.handover_status === 'active'))
const summary = computed(() => {
  const all = chips.value.map(chipLabel).join(', ')
  return props.card.delivery === 'delivered' ? `Delivered: ${all}` : `Handed over: ${all}`
})
</script>

<style scoped>
.bud-chips {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.bud-chips__chip,
.bud-chips__done {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font: 500 11px var(--font-mono);
  color: rgb(var(--v-theme-on-surface-variant));
}
.bud-chips__done {
  color: rgb(var(--v-theme-success));
}
.bud-chips__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
</style>
