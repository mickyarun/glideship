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

<!-- One Trello member and who they are here: matched, suggested by name
     (to confirm), or left unassigned. Only people who can open the target
     board are offered. -->
<template>
  <div class="person-row" role="group" :aria-label="`Trello member ${row.member.full_name}`">
    <div class="person-row__source">
      <span class="person-row__name">{{ row.member.full_name || row.member.username }}</span>
      <span v-if="row.member.username" class="person-row__meta">@{{ row.member.username }}</span>
    </div>
    <v-autocomplete
      :model-value="row.userId ?? UNASSIGNED"
      :items="items"
      label="Person here"
      density="compact"
      hide-details
      class="person-row__pick"
      @update:model-value="(id: string | null) => emit('pick', id || null)"
    />
    <div class="person-row__state">
      <AppTag :color="TONE[state]">{{ LABEL[state] }}</AppTag>
      <v-btn
        v-if="state === 'suggested'"
        size="small"
        variant="text"
        :aria-label="`Confirm ${row.member.full_name} is ${nameOf(row.userId)}`"
        @click="emit('pick', row.userId)"
      >
        Confirm
      </v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppTag from '@/components/common/AppTag.vue'
import type { PickablePerson } from '@/composables/useImportMappingForm'
import { personState, type PersonRow, type PersonState } from '@/utils/importMapping'

const props = defineProps<{ row: PersonRow; people: PickablePerson[] }>()
const emit = defineEmits<{ pick: [userId: string | null] }>()

const UNASSIGNED = ''
const TONE: Record<PersonState, string> = { matched: 'success', suggested: 'warning', unassigned: 'on-surface-variant' }
const LABEL: Record<PersonState, string> = { matched: 'Matched', suggested: 'Suggested · confirm', unassigned: 'Unassigned' }

const state = computed(() => personState(props.row))
const items = computed(() => [
  { title: 'Leave unassigned', value: UNASSIGNED },
  ...props.people.map(p => ({ title: p.name, value: p.id })),
])
const nameOf = (id: string | null) => props.people.find(p => p.id === id)?.name ?? 'this person'
</script>

<style scoped>
.person-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr) auto;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid rgb(var(--v-theme-rule));
}
.person-row:last-child {
  border-bottom: 0;
}
.person-row__source {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.person-row__name {
  font-size: 14px;
  overflow-wrap: anywhere;
}
.person-row__meta {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.person-row__state {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 120px;
}
@media (max-width: 760px) {
  .person-row {
    grid-template-columns: minmax(0, 1fr);
    gap: 8px;
  }
}
</style>
