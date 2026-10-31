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

<!-- Cards done each week, oldest first, the current week in the full
     primary colour; the same bars as Learnings' "Shipped per week". Screen
     readers get the numbers as a table instead of the bars. -->
<template>
  <AppPanel title="Throughput" :note="`Cards done each week, last ${plural(bars.length, 'week')}`">
    <p v-if="!total" class="throughput__empty" role="status">
      No cards reached a done stage in the last {{ plural(bars.length, 'week') }}.
    </p>
    <template v-else>
      <div class="throughput" aria-hidden="true">
        <span v-for="(bar, i) in bars" :key="bar.weekStart" class="throughput__week" :title="`Week of ${bar.label}: ${bar.count} done`">
          <span class="throughput__n">{{ bar.count }}</span>
          <span
            class="throughput__bar"
            :class="{ 'throughput__bar--now': i === bars.length - 1 }"
            :style="{ height: `calc((100% - 24px) * ${bar.count / peak})` }"
          />
        </span>
      </div>
      <div class="throughput throughput--labels" aria-hidden="true">
        <span
          v-for="(bar, i) in bars"
          :key="bar.weekStart"
          class="throughput__label"
          :class="{
            'throughput__label--skip': (bars.length - 1 - i) % 2 === 1,
            'throughput__label--narrow-skip': (bars.length - 1 - i) % 4 !== 0,
          }"
        >{{ bar.label }}</span>
      </div>
      <table class="d-sr-only">
        <caption>Cards done each week, oldest first</caption>
        <thead><tr><th scope="col">Week of</th><th scope="col">Cards done</th></tr></thead>
        <tbody>
          <tr v-for="bar in bars" :key="bar.weekStart"><td>{{ bar.label }}</td><td>{{ bar.count }}</td></tr>
        </tbody>
      </table>
    </template>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { WeekCount } from '@/types/boards'
import { throughputBars } from '@/utils/boardMetrics'
import { plural } from '@/utils/format'

const props = defineProps<{ weeks: WeekCount[] }>()

const bars = computed(() => throughputBars(props.weeks))
const total = computed(() => bars.value.reduce((sum, b) => sum + b.count, 0))
const peak = computed(() => Math.max(1, ...bars.value.map(b => b.count)))
</script>

<style scoped>
.throughput {
  display: grid;
  grid-template-columns: repeat(v-bind('bars.length'), minmax(0, 1fr));
  gap: 6px;
  align-items: end;
  height: 150px;
  padding-top: 8px;
}
.throughput--labels {
  height: auto;
}
.throughput__week {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  height: 100%;
  min-width: 0;
}
.throughput__n {
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: rgb(var(--v-theme-ink-2));
}
.throughput__bar {
  width: 100%;
  min-height: 3px;
  border-radius: 5px 5px 2px 2px;
  background: rgba(var(--v-theme-primary), 0.4);
}
.throughput__bar--now {
  background: rgb(var(--v-theme-primary));
}
.throughput__label {
  font-size: 11px;
  text-align: center;
  white-space: nowrap;
  color: rgb(var(--v-theme-on-surface-variant));
}
/* Every other week is labelled, counting back from this week; every
   fourth on a phone, so the dates never crowd. */
.throughput__label--skip {
  visibility: hidden;
}
@media (max-width: 600px) {
  .throughput__label--narrow-skip {
    visibility: hidden;
  }
}
.throughput__empty {
  margin: 0;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
