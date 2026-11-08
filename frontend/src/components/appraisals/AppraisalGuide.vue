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

<!-- "How this works": a button and the one-page guide it opens. The year
     at a glance is worded from the running cycle (or the org's settings);
     the rest is the plain-text guide for each audience. The button sits in
     each appraisal screen's actions. -->
<template>
  <v-btn variant="text" prepend-icon="mdi-help-circle-outline" @click="show">How this works</v-btn>
  <v-dialog v-model="open" max-width="760" scrollable>
    <v-card>
      <v-card-title class="guide__title">How appraisals work here</v-card-title>
      <v-card-text>
        <AppCallout v-if="error" variant="error">{{ error }}</AppCallout>
        <AppCallout v-if="guide?.intro_note" variant="info" title="A note from HR">{{ guide.intro_note }}</AppCallout>
        <section v-if="guide" class="guide__glance" aria-label="The period at a glance">
          <p>{{ glance }}</p>
          <p v-if="dates">{{ dates }}</p>
        </section>
        <AppPillToggle v-model="audience" :options="audiences" aria-label="Guide for" />
        <GuideSection v-for="(block, i) in blocks" :key="i" :block="block" />
        <template v-if="audience === 'everyone'">
          <h3 class="guide__heading">The five bands</h3>
          <ol class="guide__bands">
            <li v-for="band in BANDS" :key="band.value"><strong>{{ band.label }}</strong> ({{ band.value }})</li>
          </ol>
        </template>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn color="primary" variant="flat" @click="open = false">Got it</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import GuideSection from '@/components/appraisals/GuideSection.vue'
import { useAppraisalGuide } from '@/composables/useAppraisalGuide'
import employeeText from '@/content/appraisalGuide/employee.txt?raw'
import everyoneText from '@/content/appraisalGuide/everyone.txt?raw'
import hrText from '@/content/appraisalGuide/hr.txt?raw'
import managerText from '@/content/appraisalGuide/manager.txt?raw'
import { BANDS } from '@/utils/appraisalBands'
import { guideGlance, guideDates } from '@/utils/appraisalGuide'
import { guideBlocks } from '@/utils/guideText'

type Audience = 'everyone' | 'employee' | 'manager' | 'hr'
const TEXT: Record<Audience, string> = {
  everyone: everyoneText,
  employee: employeeText,
  manager: managerText,
  hr: hrText,
}

const { open, guide, error, show } = useAppraisalGuide()
const audience = ref<Audience>('everyone')
const audiences = [
  { label: 'Everyone', value: 'everyone' as Audience },
  { label: 'Employees', value: 'employee' as Audience },
  { label: 'Managers', value: 'manager' as Audience },
  { label: 'HR', value: 'hr' as Audience },
]
const blocks = computed(() => guideBlocks(TEXT[audience.value]))
const glance = computed(() => (guide.value ? guideGlance(guide.value) : ''))
const dates = computed(() => (guide.value ? guideDates(guide.value) : ''))

// Start on the tab that fits the reader best; every tab stays open to all.
watch(guide, value => {
  if (value) audience.value = value.is_hr ? 'hr' : value.is_manager ? 'manager' : 'everyone'
})
</script>

<style scoped>
.guide__title {
  font-size: 18px;
  font-weight: 600;
}
.guide__glance p {
  margin: 0 0 8px;
}
.guide__heading {
  margin: 16px 0 4px;
  font-size: 15px;
  font-weight: 600;
}
.guide__bands {
  margin: 0;
  padding-left: 20px;
}
</style>
