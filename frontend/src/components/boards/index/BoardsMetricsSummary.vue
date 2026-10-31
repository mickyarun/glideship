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

<!-- The same numbers for every board I can open, one row each, sortable
     by any column (a second click flips the order). Each board's name
     opens its metrics page. Only boards the server says I can see come back. -->
<template>
  <AppPanel title="Flow across boards" :note="`Done in the last ${plural(window.weeks, 'week')} · cycle time over ${plural(window.window_days, 'day')}`" flush>
    <div class="summary-scroll" role="region" aria-label="Flow across boards, scrolls sideways on small screens" tabindex="0">
      <table class="summary">
        <caption class="d-sr-only">Throughput, cycle time, work in progress and aging cards for each board</caption>
        <thead>
          <tr>
            <th v-for="col in COLUMNS" :key="col.by" scope="col" :aria-sort="ariaSort(col.by)" :class="{ 'summary__num': col.by !== 'name' }">
              <button type="button" class="summary__sort" @click="sortBy(col.by)">
                {{ col.label }}
                <v-icon v-if="by === col.by" :icon="descending ? 'mdi-arrow-down' : 'mdi-arrow-up'" size="14" aria-hidden="true" />
              </button>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in sorted" :key="row.key">
            <td>
              <router-link :to="{ name: 'board-metrics', params: { key: row.key } }" class="summary__board">{{ row.name }}</router-link>
              <span class="summary__key">{{ row.key }}</span>
            </td>
            <td class="summary__num">{{ throughputTotal(row) }}</td>
            <td class="summary__num">{{ formatHours(row.cycle_time.median_hours) }}</td>
            <td class="summary__num">{{ row.wip.in_progress }}</td>
            <td class="summary__num" :class="{ 'summary__warn': row.aging_count > 0 }">{{ row.aging_count }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { BoardMetricsRow, MetricsWindow } from '@/types/boards'
import { formatHours, sortSummary, throughputTotal, type SummarySort } from '@/utils/boardMetrics'
import { plural } from '@/utils/format'

const COLUMNS: { by: SummarySort; label: string }[] = [
  { by: 'name', label: 'Board' },
  { by: 'throughput', label: 'Throughput' },
  { by: 'cycle', label: 'Cycle time (median)' },
  { by: 'wip', label: 'In progress' },
  { by: 'aging', label: 'Aging' },
]

const props = defineProps<{ rows: BoardMetricsRow[]; window: MetricsWindow }>()

const by = ref<SummarySort>('name')
const descending = ref(false)
const sorted = computed(() => sortSummary(props.rows, by.value, descending.value))

function sortBy(next: SummarySort): void {
  if (by.value === next) {
    descending.value = !descending.value
    return
  }
  by.value = next
  // Names read A to Z; numbers biggest first.
  descending.value = next !== 'name'
}

function ariaSort(col: SummarySort): 'ascending' | 'descending' | 'none' {
  if (by.value !== col) return 'none'
  return descending.value ? 'descending' : 'ascending'
}
</script>

<style scoped>
.summary-scroll {
  overflow-x: auto;
}
.summary {
  width: 100%;
  min-width: 520px;
  border-collapse: collapse;
  font-size: 14px;
}
.summary th {
  padding: 6px 16px;
  text-align: left;
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--v-theme-on-surface-variant));
  white-space: nowrap;
}
.summary td {
  padding: 10px 16px;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.summary .summary__num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.summary__sort {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 0;
  font: inherit;
  color: inherit;
  background: none;
  border: 0;
  cursor: pointer;
}
.summary__sort:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
.summary__board {
  color: var(--color-accent-text);
  text-decoration: none;
}
.summary__board:hover {
  text-decoration: underline;
}
.summary__key {
  margin-left: 8px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.summary__warn {
  color: var(--color-warning);
  font-weight: 600;
}
</style>
