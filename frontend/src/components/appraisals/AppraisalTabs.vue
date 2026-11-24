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

<!-- The tab strip at the top of every appraisal page: "Your team" for
     managers, "Your own" for everyone, "Cycles" for HR. Hidden when there
     is only one tab to show. -->
<template>
  <nav v-if="tabs.length > 1" class="appraisal-tabs" aria-label="Appraisals">
    <RouterLink
      v-for="tab in tabs"
      :key="tab.key"
      :to="{ name: tab.route }"
      class="appraisal-tabs__tab"
      :class="{ 'appraisal-tabs__tab--on': tab.key === active }"
      :aria-current="tab.key === active ? 'page' : undefined"
    >
      {{ tab.label }}
    </RouterLink>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { appraisalTabs, tabForRoute } from '@/utils/appraisalTabs'

const props = withDefaults(defineProps<{ hasReports: boolean; canManage: boolean; ownPage?: boolean }>(), { ownPage: false })

const route = useRoute()
const tabs = computed(() => appraisalTabs({ hasReports: props.hasReports, canManage: props.canManage }))
const active = computed(() => tabForRoute(route.name ? String(route.name) : null, props.ownPage))
</script>

<style scoped>
.appraisal-tabs {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  border-bottom: 1px solid rgb(var(--v-theme-rule));
}
.appraisal-tabs__tab {
  padding: 10px 14px;
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  text-decoration: none;
  color: rgb(var(--v-theme-on-surface-variant));
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.appraisal-tabs__tab:hover {
  color: rgb(var(--v-theme-on-surface));
}
.appraisal-tabs__tab:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: -2px;
}
.appraisal-tabs__tab--on {
  color: rgb(var(--v-theme-primary));
  border-bottom-color: rgb(var(--v-theme-primary));
}
</style>
