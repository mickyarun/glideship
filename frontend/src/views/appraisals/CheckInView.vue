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

<!-- One check-in by id: a manager reading a report's month, or HR. The
     API answers "not found" for anyone else. -->
<template>
  <AppPage :title="title" :subtitle="subtitle">
    <template #eyebrow>
      <router-link :to="{ name: 'appraisal-team' }" class="check-in-view__back">Team check-ins</router-link>
    </template>
    <AppCallout v-if="store.error" variant="error">{{ store.error }}</AppCallout>
    <v-progress-linear v-if="store.loading && !store.current" indeterminate color="primary" />
    <CheckInPage v-if="store.current" :check-in="store.current" />
  </AppPage>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import CheckInPage from '@/components/appraisals/CheckInPage.vue'
import { useCheckInsStore } from '@/stores/checkIns'
import { availabilityLine, monthTitle } from '@/utils/appraisalCheckIn'

const route = useRoute()
const store = useCheckInsStore()

const title = computed(() =>
  store.current ? `${store.current.person_name}'s ${monthTitle(store.current.period_start)}` : 'Check-in',
)
const subtitle = computed(() =>
  store.current ? `${availabilityLine(store.current)} · Only ${store.current.person_name} writes here` : '',
)

watch(
  () => route.params.id,
  id => {
    store.current = null
    if (typeof id === 'string') void store.fetchOne(id)
  },
  { immediate: true },
)
</script>

<style scoped>
.check-in-view__back {
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
