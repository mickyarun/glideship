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

<!-- One role's side of "How appraisals work": four numbered steps through a
     period, then who sees what. -->
<template>
  <section class="role">
    <h3 class="role__heading">{{ heading }}</h3>
    <ol class="role__steps">
      <li v-for="(step, i) in steps" :key="i" class="role__step">
        <span class="role__number" aria-hidden="true">{{ i + 1 }}</span>
        <span><strong>{{ step.lead }}</strong> {{ step.rest }}</span>
      </li>
    </ol>
    <h3 class="role__heading">Who sees what</h3>
    <ul class="role__lines">
      <li v-for="(line, i) in lines" :key="i"><strong>{{ line.lead }}</strong> {{ line.rest }}</li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import type { GuidePart } from '@/utils/appraisalGuide'

defineProps<{ heading: string; steps: GuidePart[]; lines: GuidePart[] }>()
</script>

<style scoped>
.role {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.role__heading {
  margin: 2px 0 0;
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface-variant));
}
.role__steps,
.role__lines {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 13.5px;
  line-height: 1.4;
}
.role__step {
  display: flex;
  gap: 10px;
  align-items: baseline;
}
.role__number {
  flex: none;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  line-height: 22px;
  text-align: center;
  background: rgb(var(--v-theme-primary), 0.12);
  color: rgb(var(--v-theme-primary));
}
</style>
