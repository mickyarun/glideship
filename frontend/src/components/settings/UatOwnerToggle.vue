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
<!--
  Who a BUD is auto-assigned to when it enters UAT: the PM (sign-off) or QA
  (teams where QA runs UAT), each with its own fallback roles. With QA as
  owner, QA may also move the BUD on to Prod or back to Development.
-->
<template>
  <div class="mb-6">
    <div class="text-body-2 font-weight-medium mb-2">UAT owner</div>
    <AppPillToggle v-model="owner" :options="OWNERS" aria-label="UAT owner" class="mb-2" />
    <div class="text-caption text-medium-emphasis">
      BUDs moving into UAT are assigned to {{ FALLBACK[owner] }} {{ MOVES[owner] }}
      BUDs already in UAT keep their assignee.
    </div>
  </div>
</template>

<script setup lang="ts">
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import type { UatOwner } from '@/stores/settings'

const OWNERS: { label: string; value: UatOwner }[] = [
  { label: 'Product manager', value: 'pm' },
  { label: 'QA', value: 'qa' },
]

// Mirrors UAT_CHAIN_BY_OWNER in backend/app/services/phase_roles.py.
const FALLBACK: Record<UatOwner, string> = {
  pm: 'a product manager, or a manager if there is none.',
  qa: 'QA, or a product manager if there is no QA, then a manager.',
}

// Mirrors _QA_UAT_OWNER_TRANSITIONS in backend/app/api/v1/bud.py.
const MOVES: Record<UatOwner, string> = {
  pm: 'A PM moves it on from UAT.',
  qa: 'QA can move it on to Prod or back to Development.',
}

const owner = defineModel<UatOwner>({ required: true })
</script>
