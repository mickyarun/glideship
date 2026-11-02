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

<!-- A board's metrics, inside the board route's shell: the headline
     numbers, throughput per week, work in progress by category and the
     cards aging in progress. Anyone who can open the board can read them. -->
<template>
  <AppPage v-if="detail" title="Metrics" :subtitle="subtitle">
    <template #eyebrow><BoardCrumbs :board="detail.board" current="Metrics" /></template>
    <template #actions>
      <v-btn variant="outlined" prepend-icon="mdi-view-column-outline" :to="{ name: 'board', params: { key: detail.board.key } }">
        Back to the board
      </v-btn>
    </template>

    <AppCallout v-if="metrics.error.value" variant="error" role="alert" title="Metrics didn't load">
      {{ metrics.error.value }}
      <template #actions>
        <v-btn variant="outlined" size="small" @click="metrics.load()">Try again</v-btn>
      </template>
    </AppCallout>
    <div v-else-if="!data" class="board-metrics" role="status" aria-label="Loading metrics">
      <v-skeleton-loader v-for="i in 3" :key="i" type="article" class="board-metrics__bone" />
    </div>
    <AppEmptyState
      v-else-if="quiet"
      icon="mdi-chart-bar"
      title="Nothing to measure yet"
      body="Numbers appear here once cards move through the board's stages."
    />
    <template v-else>
      <LearningsKpiRow :kpis="kpis" />
      <ThroughputChart :weeks="data.throughput" />
      <div class="board-metrics__pair">
        <WipByCategory :wip="data.wip" />
        <AgingList
          :board-key="detail.board.key"
          :cards="data.aging"
          :total="data.aging_count"
          :aging-days="data.window.aging_days"
          :now="now"
        />
      </div>
    </template>
  </AppPage>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BoardCrumbs from '@/components/boards/BoardCrumbs.vue'
import AgingList from '@/components/boards/metrics/AgingList.vue'
import ThroughputChart from '@/components/boards/metrics/ThroughputChart.vue'
import WipByCategory from '@/components/boards/metrics/WipByCategory.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppEmptyState from '@/components/common/AppEmptyState.vue'
import AppPage from '@/components/common/AppPage.vue'
import LearningsKpiRow from '@/components/learnings/LearningsKpiRow.vue'
import { useBoardContext } from '@/composables/useBoardContext'
import { useBoardMetrics } from '@/composables/useBoardMetrics'
import { useNow } from '@/composables/useNow'
import { metricsKpis, throughputTotal } from '@/utils/boardMetrics'
import { plural } from '@/utils/format'

const page = useBoardContext()
const now = useNow()
const detail = computed(() => page.board.detail.value)
const metrics = useBoardMetrics(computed(() => detail.value?.board.key ?? ''))
const data = computed(() => metrics.data.value)

const kpis = computed(() => (data.value ? metricsKpis(data.value, data.value.window) : []))
/** No card has ever moved: one empty state instead of four empty panels. */
const quiet = computed(() => {
  const d = data.value
  if (!d) return false
  const open = Object.values(d.wip).reduce((sum, n) => sum + n, 0)
  return !open && !throughputTotal(d) && !d.cycle_time.count && !d.lead_time.count
})
const subtitle = computed(() => {
  const name = detail.value?.board.name ?? ''
  const window = data.value?.window
  return window ? `${name} · cycle and lead times over the last ${plural(window.window_days, 'day')}` : name
})
</script>

<style scoped>
.board-metrics {
  display: grid;
  gap: 12px;
}
.board-metrics__bone {
  border-radius: 12px;
}
.board-metrics__pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  align-items: start;
}
@media (max-width: 900px) {
  .board-metrics__pair {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
