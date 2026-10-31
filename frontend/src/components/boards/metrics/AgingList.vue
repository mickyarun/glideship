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

<!-- Cards in progress for longer than the board's aging limit, oldest
     first, each linking to its card page with how long since it started. -->
<template>
  <AppPanel title="Aging" :note="`In progress over ${plural(agingDays, 'day')}`" flush>
    <p v-if="!cards.length" class="aging__empty" role="status">
      Nothing has been in progress for over {{ plural(agingDays, 'day') }}.
    </p>
    <table v-else class="aging">
      <caption class="d-sr-only">Cards in progress the longest, oldest first</caption>
      <thead>
        <tr><th scope="col">Card</th><th scope="col" class="aging__age">Age (since started)</th></tr>
      </thead>
      <tbody>
        <tr v-for="card in rows" :key="card.key">
          <td class="aging__card">
            <router-link v-if="card.to" :to="card.to" class="aging__key">{{ card.key }}</router-link>
            <span v-else class="aging__key">{{ card.key }}</span>
            <span class="aging__title">{{ card.title }}</span>
          </td>
          <td class="aging__age" :title="new Date(card.since).toLocaleString()">{{ card.age }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="more > 0" class="aging__more">and {{ plural(more, 'more card') }}</p>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { AgingCard } from '@/types/boards'
import { formatHours, hoursSince } from '@/utils/boardMetrics'
import { cardRouteByKey } from '@/utils/boardRoutes'
import { plural } from '@/utils/format'

const props = defineProps<{
  boardKey: string
  cards: AgingCard[]
  /** Every aging card, of which ``cards`` are the oldest. */
  total: number
  agingDays: number
  now: Date
}>()

const rows = computed(() =>
  props.cards.map(card => ({
    ...card,
    to: cardRouteByKey(props.boardKey, card.key),
    age: formatHours(hoursSince(card.since, props.now)),
  })),
)
const more = computed(() => props.total - props.cards.length)
</script>

<style scoped>
.aging {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.aging th {
  padding: 8px 16px;
  text-align: left;
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--v-theme-on-surface-variant));
}
.aging td {
  padding: 10px 16px;
  border-top: 1px solid rgb(var(--v-theme-rule));
  vertical-align: baseline;
}
.aging__card {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  min-width: 0;
}
.aging__key {
  flex: none;
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--color-accent-text);
  text-decoration: none;
}
a.aging__key:hover {
  text-decoration: underline;
}
.aging__title {
  min-width: 0;
  overflow-wrap: anywhere;
}
.aging .aging__age {
  width: 1%;
  text-align: right;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.aging__empty,
.aging__more {
  margin: 0;
  padding: 12px 16px;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
