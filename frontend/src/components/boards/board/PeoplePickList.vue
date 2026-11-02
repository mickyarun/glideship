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

<!-- The people picker every assignee control shares: a search box over a
     checklist of people (photo or initials, and how their access reads,
     "via Writers"). Each pick toggles at once; the list stays for the
     next. Lives inside a menu its caller owns. -->
<template>
  <v-card min-width="260" max-width="320" elevation="8" class="people-pick">
    <v-text-field
      v-model="query"
      label="Search people"
      prepend-inner-icon="mdi-magnify"
      density="compact"
      hide-details
      autofocus
      class="ma-2"
    />
    <v-list density="compact" max-height="280" role="listbox" aria-multiselectable="true" :aria-label="label">
      <v-list-item v-if="!shown.length" :title="query ? 'No one matches' : emptyText" disabled />
      <v-list-item
        v-for="p in shown"
        :key="p.id"
        role="option"
        :aria-selected="selected.includes(p.id)"
        @click="emit('toggle', p.id)"
      >
        <template #prepend>
          <v-icon
            :icon="selected.includes(p.id) ? 'mdi-checkbox-marked' : 'mdi-checkbox-blank-outline'"
            size="18"
            class="mr-2"
            aria-hidden="true"
          />
          <AppMonogram :name="p.name" :src="p.photo" :size="22" class="mr-2" />
        </template>
        <v-list-item-title>{{ p.name }}</v-list-item-title>
        <v-list-item-subtitle v-if="p.note" class="people-pick__note">{{ p.note }}</v-list-item-subtitle>
      </v-list-item>
    </v-list>
  </v-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import AppMonogram from '@/components/common/AppMonogram.vue'
import type { PickPerson } from '@/utils/boardPeople'

const props = withDefaults(
  defineProps<{ people: PickPerson[]; selected: string[]; label: string; emptyText?: string }>(),
  { emptyText: 'No one else can open this board' },
)
const emit = defineEmits<{ toggle: [id: string] }>()

const query = ref('')
const shown = computed(() => {
  const q = query.value.trim().toLowerCase()
  return q ? props.people.filter(p => p.name.toLowerCase().includes(q)) : props.people
})
</script>

<style scoped>
.people-pick__note {
  font-size: 12px;
}
</style>
