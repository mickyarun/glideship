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

<!-- Team check-ins: each direct report's latest check-in. Managers read
     them here; feedback goes in manager feedback, not in the check-in. -->
<template>
  <AppPage title="Your team's check-ins" subtitle="The latest month for each person who reports to you.">
    <AppCallout v-if="store.listError" variant="error">{{ store.listError }}</AppCallout>
    <v-progress-linear v-if="store.listLoading" indeterminate color="primary" />
    <p v-else-if="!store.team.length" class="team__empty">Nobody who reports to you has a check-in yet.</p>
    <ul v-else class="team__list">
      <li v-for="row in store.team" :key="row.id">
        <router-link :to="{ name: 'appraisal-check-in', params: { id: row.id } }" class="team__row">
          <span class="team__name">{{ row.person_name }}</span>
          <span class="team__meta">{{ monthTitle(row.period_start) }} · {{ statusLabel(row.status, row.closed) }} · {{ row.fact_count }} items recorded</span>
        </router-link>
      </li>
    </ul>
  </AppPage>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import { useCheckInsStore } from '@/stores/checkIns'
import { monthTitle, statusLabel } from '@/utils/appraisalCheckIn'

const store = useCheckInsStore()

onMounted(() => {
  void store.fetchTeam()
})
</script>

<style scoped>
.team__empty {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.team__list {
  margin: 0;
  padding: 0;
  list-style: none;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
  overflow: hidden;
}
.team__list li + li {
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.team__row {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 16px;
  color: inherit;
  text-decoration: none;
}
.team__row:hover {
  background: rgba(var(--v-theme-on-surface), 0.04);
}
.team__name {
  font-weight: 600;
}
.team__meta {
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
