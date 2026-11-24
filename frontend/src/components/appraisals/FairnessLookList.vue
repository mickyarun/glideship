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

<!-- What needs a look in the fairness check: big differences, managers who
     rate high, flagged concerns. Each can be sent back to its manager or
     marked "Looks fair", which lets it be shared; once marked, it says by
     whom and when. -->
<template>
  <AppPanel :title="`Needs a look · ${open}`" flush>
    <p v-if="!items.length" class="look__muted look__empty">Nothing stands out.</p>
    <ul class="look__list">
      <li v-for="item in items" :key="item.key" class="look__item">
        <div class="look__words"><strong>{{ item.title }}</strong><span class="look__muted">{{ item.detail }}</span></div>
        <span class="look__tag">{{ item.tag }}</span>
        <div class="look__actions">
          <span v-if="item.fairAt" class="look__muted">Looks fair · {{ item.fairBy || 'HR' }}, {{ longDate(localDay(item.fairAt)) }}</span>
          <template v-else>
            <v-btn v-if="item.canSendBack" size="small" variant="text" @click="emit('send-back', item)">Send back to {{ firstName(item.managerName, 'the manager') }}</v-btn>
            <v-btn v-if="item.fairIds.length" size="small" variant="outlined" :loading="busy === item.key" @click="emit('fair', item)">Looks fair</v-btn>
          </template>
          <v-btn v-if="item.appraisalId" size="small" variant="text" :to="{ name: 'appraisal-review', params: { id: item.appraisalId } }">
            Open review<span class="d-sr-only"> for {{ item.title }}</span>
          </v-btn>
        </div>
      </li>
    </ul>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { localDay } from '@/utils/appraisalCheckIn'
import type { LookItem } from '@/utils/appraisalFairness'
import { firstName } from '@/utils/appraisalReview'
import { longDate } from '@/utils/appraisalSetup'

const props = defineProps<{ items: LookItem[]; busy: string | null }>()
const emit = defineEmits<{ 'send-back': [item: LookItem]; fair: [item: LookItem] }>()
const open = computed(() => props.items.filter(i => !i.fairAt).length)
</script>

<style scoped>
.look__list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.look__item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 12px 20px;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.look__words {
  display: flex;
  flex: 1 1 280px;
  flex-direction: column;
  font-size: 14px;
}
.look__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.look__muted {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.look__empty {
  padding: 0 20px 16px;
}
.look__tag {
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--v-theme-warning));
}
</style>
