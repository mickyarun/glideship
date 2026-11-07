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

<!-- HR's appraisal cycles, newest first. A new cycle starts as a draft for
     the next period, prefilled from the settings; it opens from its page. -->
<template>
  <AppPage title="Appraisal cycles" subtitle="Set up a cycle, check who's ready, open it and follow it through.">
    <template #actions>
      <v-btn variant="text" :to="{ name: 'appraisal-settings' }">Settings</v-btn>
      <AppraisalGuide />
      <v-btn color="primary" prepend-icon="mdi-plus" :loading="creating" @click="create">New cycle</v-btn>
    </template>
    <AppCallout v-if="store.error || problem" variant="error">{{ problem || store.error }}</AppCallout>
    <v-progress-linear v-if="store.loading && !store.cycles.length" indeterminate color="primary" />
    <p v-else-if="!store.cycles.length" class="cycles__empty">
      No cycles yet. A new one is set up for the next period from your appraisal settings.
    </p>
    <ul v-else class="cycles__list">
      <li v-for="cycle in store.cycles" :key="cycle.id">
        <router-link :to="{ name: 'appraisal-cycle', params: { id: cycle.id } }" class="cycles__row">
          <span class="cycles__name">{{ cycle.name }}</span>
          <span class="cycles__meta">{{ longDate(cycle.period_start) }} – {{ longDate(cycle.period_end) }}</span>
          <span class="cycles__status" :class="`cycles__status--${cycle.status}`">{{ CYCLE_STATUS[cycle.status] }}</span>
        </router-link>
      </li>
    </ul>
  </AppPage>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppraisalGuide from '@/components/appraisals/AppraisalGuide.vue'
import { useAppraisalSetupStore } from '@/stores/appraisalSetup'
import { CYCLE_STATUS, longDate } from '@/utils/appraisalSetup'

const store = useAppraisalSetupStore()
const router = useRouter()
const creating = ref(false)
const problem = ref('')

async function create(): Promise<void> {
  creating.value = true
  const [cycle, failed] = await store.createCycle({})
  creating.value = false
  problem.value = failed ?? ''
  if (cycle) await router.push({ name: 'appraisal-cycle', params: { id: cycle.id } })
}

onMounted(() => {
  void store.fetchCycles()
})
</script>

<style scoped>
.cycles__empty {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.cycles__list {
  margin: 0;
  padding: 0;
  list-style: none;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
  overflow: hidden;
}
.cycles__list li + li {
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.cycles__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  padding: 14px 16px;
  color: inherit;
  text-decoration: none;
}
.cycles__row:hover {
  background: rgba(var(--v-theme-on-surface), 0.04);
}
.cycles__name {
  flex: 1 1 120px;
  font-weight: 600;
}
.cycles__meta,
.cycles__status {
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.cycles__status--active,
.cycles__status--reviewing {
  color: rgb(var(--v-theme-primary));
  font-weight: 600;
}
</style>
