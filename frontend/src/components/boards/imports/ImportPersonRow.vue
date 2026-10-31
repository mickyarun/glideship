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

<!-- One Trello member and who they are here: matched (the one person
     with their full name, or picked), suggested (to confirm), or left
     unassigned. The name and its state share the first line, the picker
     the whole second one. Only people who can open the target board are
     offered; a suggestion not in that list shows as an unknown person,
     never as an id. -->
<template>
  <div class="person-row" role="group" :aria-label="`Trello member ${memberName}`">
    <div class="person-row__source">
      <span class="person-row__name">{{ memberName }}</span>
      <span v-if="row.member.username" class="person-row__meta">@{{ row.member.username }}</span>
    </div>
    <div class="person-row__state">
      <AppTag :color="TONE[state]">{{ LABEL[state] }}</AppTag>
      <v-btn
        v-if="state === 'suggested'"
        size="small"
        variant="text"
        :aria-label="`Confirm ${memberName} is ${shownName}`"
        @click="confirm"
      >
        Confirm
      </v-btn>
    </div>
    <v-autocomplete
      ref="picker"
      :model-value="row.userId ?? UNASSIGNED"
      :items="items"
      :aria-label="`Person here for ${memberName}`"
      density="compact"
      hide-details
      class="person-row__pick"
      @update:model-value="(id: string | null) => emit('pick', id || null)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, useTemplateRef } from 'vue'
import AppTag from '@/components/common/AppTag.vue'
import type { PickablePerson } from '@/composables/useImportMappingForm'
import { personState, type PersonRow, type PersonState } from '@/utils/importMapping'

const props = defineProps<{ row: PersonRow; people: PickablePerson[] }>()
const emit = defineEmits<{ pick: [userId: string | null] }>()

const UNASSIGNED = ''
const UNKNOWN = 'Unknown person'
const TONE: Record<PersonState, string> = { matched: 'success', suggested: 'warning', unassigned: 'on-surface-variant' }
const LABEL: Record<PersonState, string> = { matched: 'Matched', suggested: 'Suggested', unassigned: 'Unassigned' }

const picker = useTemplateRef<{ $el: HTMLElement }>('picker')
const memberName = computed(() => props.row.member.full_name || props.row.member.username)
const person = computed(() => props.people.find(p => p.id === props.row.userId) ?? null)
const shownName = computed(() => person.value?.name ?? `${memberName.value} (${UNKNOWN.toLowerCase()})`)
// Without the people list a suggestion can't be checked by name; the server's is a full-name match.
const state = computed(() => personState(props.row, props.people.length ? person.value?.name ?? UNKNOWN : null))
const items = computed(() => [
  { title: 'Leave unassigned', value: UNASSIGNED },
  ...props.people.map(p => ({ title: p.name, value: p.id })),
  ...(props.row.userId && !person.value ? [{ title: `${memberName.value} · ${UNKNOWN}`, value: props.row.userId }] : []),
])

/** Keep the suggestion, then put focus on the picker the Confirm button leaves. */
function confirm(): void {
  emit('pick', props.row.userId)
  void nextTick(() => picker.value?.$el.querySelector('input')?.focus())
}
</script>

<style scoped>
.person-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px;
  align-items: center;
  gap: 8px 12px;
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
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}
.person-row__pick {
  grid-column: 1 / -1;
}
</style>
