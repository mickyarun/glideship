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

<!-- Each manager's reviews in the fairness check: how many are in, how
     they rated from lowest to highest, how often they kept the person's
     own rating, big differences, and where they stand. -->
<template>
  <AppPanel title="By manager" flush>
    <div class="ft__scroll">
      <table class="ft">
        <thead>
          <tr>
            <th scope="col">Manager</th>
            <th scope="col">Reviews in</th>
            <th scope="col">How they rated <span class="ft__muted">lowest → highest</span></th>
            <th scope="col">Agreed with the person</th>
            <th scope="col">Big differences</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="team in calibration.teams" :key="team.manager_name">
            <td>{{ team.manager_name }}</td>
            <td>{{ team.people }}/{{ team.total }}</td>
            <td>
              <span class="ft__spread" :aria-label="spreadLabel(team)">
                <span v-for="(n, i) in spread(team)" :key="i" class="ft__count">{{ n }}</span>
              </span>
            </td>
            <td>{{ team.agreement === null ? '–' : `${Math.round(team.agreement * team.people)} of ${team.people}` }}</td>
            <td>{{ team.people ? team.gaps : '–' }}</td>
            <td>{{ teamStatus(team, calibration, high) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="ft__key">"Big difference" means two or more steps apart on the five-step scale. Agreed means the manager kept the person's own overall rating.</p>
  </AppPanel>
</template>

<script setup lang="ts">
import AppPanel from '@/components/common/AppPanel.vue'
import type { Calibration, CalibrationTeam } from '@/types/appraisalReview'
import { BANDS } from '@/utils/appraisalBands'
import { spread, teamStatus } from '@/utils/appraisalFairness'

defineProps<{ calibration: Calibration; high: Set<string> }>()

function spreadLabel(team: CalibrationTeam): string {
  return spread(team).map((n, i) => `${BANDS[i].label} ${n}`).join(', ')
}
</script>

<style scoped>
.ft__scroll {
  overflow-x: auto;
}
.ft {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.ft th,
.ft td {
  padding: 10px 20px;
  text-align: left;
  border-top: 1px solid rgb(var(--v-theme-rule));
  white-space: nowrap;
}
.ft th {
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface-variant));
}
.ft__muted {
  font-weight: 400;
}
.ft__spread {
  display: inline-flex;
  gap: 4px;
}
.ft__count {
  min-width: 22px;
  padding: 2px 6px;
  border-radius: var(--radius-input);
  background: var(--color-accent-soft);
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.ft__key {
  margin: 0;
  padding: 12px 20px 16px;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
