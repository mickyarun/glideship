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

<!-- The Garden on its own page, for board users outside the engineering
     workspace (engineers have it on the dashboard; the route sends them
     there). The world and the org's people, with cards finished and work
     handed over showing up as it happens; no code map, which is
     engineering data. -->
<template>
  <div class="garden-page">
    <header class="garden-page__head">
      <h1 class="garden-page__title">Garden</h1>
      <p class="garden-page__sub">Your team's world. Cards finished and work handed over show up here as they happen.</p>
      <v-btn variant="outlined" prepend-icon="mdi-account-edit-outline" :to="{ name: 'character-select' }">
        Customize character
      </v-btn>
    </header>
    <CanvasStage
      v-if="world"
      ref="stageRef"
      mode="garden"
      :loading="false"
      :data="world"
      :tree-data="world"
      :visible-repos="[]"
      :in-control="takeover.inControl.value"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useGardenTakeover } from '@/composables/useGardenTakeover'
import { useAuthStore } from '@/stores/auth'
import { worldWithoutCode } from '@/utils/gardenWorld'
import CanvasStage from '@/views/dashboard/CanvasStage.vue'

const auth = useAuthStore()
const stageRef = ref<InstanceType<typeof CanvasStage> | null>(null)
const takeover = useGardenTakeover(stageRef, () => true)

// One world per org: a new object only when the org changes, so the
// canvas doesn't rebuild the scene on every render.
const orgId = computed(() => auth.user?.org_id ?? null)
const world = computed(() => (orgId.value ? worldWithoutCode(orgId.value) : null))
</script>

<style scoped>
.garden-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  padding: 28px 36px 16px;
  background: rgb(var(--v-theme-background));
}
.garden-page__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
}
.garden-page__title {
  margin: 0;
  font-size: 28px;
  line-height: 34px;
  font-weight: 600;
  letter-spacing: var(--tracking-display);
}
.garden-page__sub {
  flex: 1 1 280px;
  margin: 0;
  font-size: var(--text-sm);
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (max-width: 600px) {
  .garden-page {
    padding: 20px 16px 16px;
  }
  .garden-page__title {
    font-size: 24px;
    line-height: 30px;
  }
}
</style>
