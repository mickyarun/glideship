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

<!-- My month: the caller's check-ins, newest first, with the latest open.
     A month picker switches between the check-ins they have. -->
<template>
  <AppPage :title="title" :subtitle="subtitle">
    <template #eyebrow><span class="my-month__eyebrow">Monthly check-in</span></template>
    <template v-if="store.mine.length > 1" #actions>
      <AppPillToggle :model-value="selected ?? ''" :options="monthOptions" aria-label="Month" @update:model-value="v => pick(String(v))" />
    </template>
    <AppCallout v-if="store.listError || store.error" variant="error">{{ store.listError || store.error }}</AppCallout>
    <v-progress-linear v-if="(store.listLoading || store.loading) && !store.current" indeterminate color="primary" />
    <p v-else-if="!store.listLoading && !store.mine.length" class="my-month__empty">
      No check-ins yet. Your first one opens on the first working day after a month in an appraisal cycle ends.
    </p>
    <CheckInPage v-if="store.current" :check-in="store.current" />
  </AppPage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import CheckInPage from '@/components/appraisals/CheckInPage.vue'
import { useCheckInsStore } from '@/stores/checkIns'
import { availabilityLine, monthTitle } from '@/utils/appraisalCheckIn'

const store = useCheckInsStore()
const selected = ref<string | null>(null)

const monthOptions = computed(() =>
  store.mine.slice(0, 6).map(c => ({ label: monthTitle(c.period_start), value: c.id })),
)
const title = computed(() => {
  const current = store.current
  if (!current) return 'My month'
  const month = monthTitle(current.period_start)
  return current.can_edit ? `Record how ${month} went` : month
})
const subtitle = computed(() => {
  const current = store.current
  if (!current) return ''
  const next = current.can_edit ? ' · Open until the next check-in opens' : ''
  return `${availabilityLine(current)}${next}`
})

async function pick(id: string): Promise<void> {
  selected.value = id
  await store.fetchOne(id)
}

onMounted(async () => {
  store.current = null
  await store.fetchMine()
  const latest = store.mine[0]
  if (latest) await pick(latest.id)
})
</script>

<style scoped>
.my-month__eyebrow {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.my-month__empty {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
