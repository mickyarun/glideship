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

<!-- "How appraisals work": a button and the short dialog it opens. The
     reader's own side shows first (HR, manager or employee) and every side
     can be read. Dates and numbers come from the running cycle and the org's
     settings; the rating words from the one band mapping. It opens only from
     the button, never by itself, and gives focus back to it on closing. -->
<template>
  <v-btn ref="opener" variant="text" prepend-icon="mdi-help-circle-outline" @click="show">How appraisals work</v-btn>
  <v-dialog v-model="open" max-width="720" :aria-labelledby="titleId" @after-enter="focusTitle" @after-leave="giveBack">
    <v-card class="guide" :elevation="0">
      <header class="guide__head">
        <h2 :id="titleId" ref="title" class="guide__title" tabindex="-1">How appraisals work</h2>
        <p v-if="subtitle" class="guide__muted">{{ subtitle }}</p>
      </header>
      <AppCallout v-if="error" variant="error">{{ error }}</AppCallout>
      <AppPillToggle v-model="role" :options="GUIDE_ROLES" pressed aria-label="Show how it works for" />
      <GuideRolePanel :heading="guideHeading(role, guide)" :steps="guideSteps(role, guide)" :lines="whoSeesWhat(role)" />
      <section>
        <h3 class="guide__heading">The five ratings, lowest to highest</h3>
        <ol class="guide__bands">
          <li v-for="band in BANDS" :key="band.value">{{ band.label }}</li>
        </ol>
      </section>
      <AppCallout variant="info">
        <strong>AI help is optional.</strong> It can draft a first version of your check-in from your recorded work, with the source of every line. It never scores or compares anyone, and you can ignore it.
      </AppCallout>
      <footer class="guide__foot">
        <span class="guide__muted">You can reopen this any time from "How appraisals work".</span>
        <v-btn color="primary" variant="flat" @click="open = false">Got it</v-btn>
      </footer>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import GuideRolePanel from '@/components/appraisals/GuideRolePanel.vue'
import { useAppraisalGuide } from '@/composables/useAppraisalGuide'
import { BANDS } from '@/utils/appraisalBands'
import { defaultRole, GUIDE_ROLES, type GuideRole, guideHeading, guideSteps, guideSubtitle, whoSeesWhat } from '@/utils/appraisalGuide'

const { open, guide, error, show } = useAppraisalGuide()
const role = ref<GuideRole>(defaultRole(guide.value))
const subtitle = computed(() => guideSubtitle(guide.value))
const titleId = useId()
const title = ref<HTMLElement | null>(null)
const opener = ref<{ $el: HTMLElement } | null>(null)

// The reader's own side each time it opens, or when the facts arrive; they can switch after.
watch([open, guide], ([isOpen, value], [wasOpen]) => {
  if ((isOpen && !wasOpen) || value) role.value = defaultRole(value)
})

function focusTitle(): void {
  title.value?.focus()
}

function giveBack(): void {
  opener.value?.$el.focus()
}
</script>

<style scoped>
.guide {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px 22px;
}
.guide__head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.guide__title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}
.guide__title:focus {
  outline: none;
}
.guide__heading {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface-variant));
}
.guide__bands {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 13px;
}
.guide__bands li {
  padding: 2px 10px;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 999px;
}
.guide__muted {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.guide__foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
