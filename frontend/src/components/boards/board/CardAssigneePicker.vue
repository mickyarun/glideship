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

<!-- Who's on a card, on its board tile. Editors get a button (the avatars,
     or a "+ person" icon when no one is assigned) that opens a searchable
     list of the people who can open the board; each pick saves at once and
     the list stays open for the next. Viewers see the avatars only. -->
<template>
  <span v-if="!canEdit" class="assignees">
    <AppMonogram
      v-for="p in assigned"
      :key="p.id"
      :name="p.name"
      :src="p.photo"
      :size="22"
      :title="p.name"
      :label="`Assigned to ${p.name}`"
    />
  </span>
  <v-menu v-else v-model="open" location="bottom end" :close-on-content-click="false">
    <template #activator="{ props: menuProps }">
      <button
        v-bind="menuProps"
        type="button"
        class="assignees assignees__trigger card-tile__quick"
        :aria-label="`Assignees for ${card.key}`"
        :title="assigned.length ? names : 'Assign someone'"
      >
        <AppMonogram v-for="p in assigned" :key="p.id" :name="p.name" :src="p.photo" :size="22" />
        <v-icon v-if="!assigned.length" icon="mdi-account-plus-outline" size="18" aria-hidden="true" />
      </button>
    </template>
    <v-card min-width="260" max-width="320" elevation="8" class="assignees__menu">
      <v-text-field
        v-model="query"
        label="Search people"
        prepend-inner-icon="mdi-magnify"
        density="compact"
        hide-details
        autofocus
        class="ma-2"
      />
      <v-list
        density="compact"
        max-height="280"
        role="listbox"
        aria-multiselectable="true"
        :aria-label="`Assignees for ${card.key}`"
      >
        <v-list-item v-if="!shown.length" :title="query ? 'No one matches' : 'No one else can open this board'" disabled />
        <v-list-item
          v-for="p in shown"
          :key="p.id"
          role="option"
          :aria-selected="card.assignee_ids.includes(p.id)"
          @click="toggle(p.id)"
        >
          <template #prepend>
            <v-icon
              :icon="card.assignee_ids.includes(p.id) ? 'mdi-checkbox-marked' : 'mdi-checkbox-blank-outline'"
              size="18"
              class="mr-2"
              aria-hidden="true"
            />
            <AppMonogram :name="p.name" :src="p.photo" :size="22" class="mr-2" />
          </template>
          <v-list-item-title>{{ p.name }}</v-list-item-title>
        </v-list-item>
      </v-list>
    </v-card>
  </v-menu>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import AppMonogram from '@/components/common/AppMonogram.vue'
import { useCardQuickEdit } from '@/composables/useCardQuickEdit'
import { useMemberDirectory } from '@/composables/useMemberDirectory'
import type { CardSummary } from '@/types/boards'
import { wordList } from '@/utils/format'

const props = defineProps<{ card: CardSummary; canEdit: boolean }>()
const emit = defineEmits<{ failed: [error: string] }>()

const quick = useCardQuickEdit()
const { nameFor, photoFor } = useMemberDirectory()
const open = ref(false)
const query = ref('')

const assigned = computed(() => props.card.assignee_ids.map(id => ({ id, name: nameFor(id), photo: photoFor(id) })))
const names = computed(() => `Assigned to ${wordList(assigned.value.map(p => p.name))}`)
// Worked out only while the list is open, so tiles don't each walk the directory.
const shown = computed(() => {
  if (!open.value) return []
  const q = query.value.trim().toLowerCase()
  const everyone = quick.people(props.card.assignee_ids)
  return q ? everyone.filter(p => p.name.toLowerCase().includes(q)) : everyone
})

async function toggle(id: string): Promise<void> {
  const ids = props.card.assignee_ids
  const next = ids.includes(id) ? ids.filter(i => i !== id) : [...ids, id]
  const error = await quick.save(props.card, { assignee_ids: next }, { assignee_ids: next })
  if (error) emit('failed', error)
}
</script>

<style scoped>
.assignees {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.assignees__trigger {
  position: relative;
  z-index: 1;
  min-height: 24px;
  min-width: 24px;
  justify-content: center;
  padding: 1px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: rgb(var(--v-theme-on-surface-variant));
  cursor: pointer;
}
.assignees__trigger:hover {
  background: rgb(var(--v-theme-surface-bright));
}
.assignees__trigger:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
@media (pointer: coarse) {
  .assignees__trigger {
    min-height: 44px;
    min-width: 44px;
  }
}
</style>
