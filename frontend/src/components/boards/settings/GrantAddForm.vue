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

<!-- Give someone a role on the board: a person from the org directory or
     a team, and the role they get. -->
<template>
  <form class="grant-add" aria-label="Add people or teams" @submit.prevent="submit">
    <v-autocomplete
      v-model="picked"
      :items="candidates"
      item-title="title"
      item-value="value"
      return-object
      :label="withTeams ? 'Add people or teams' : 'Add people'"
      placeholder="Name, email or team"
      :custom-filter="matches"
      :disabled="disabled"
      density="compact"
      hide-details
      class="grant-add__who"
    >
      <template #item="{ item, props: itemProps }">
        <v-list-item v-bind="itemProps" :subtitle="item.raw.subtitle">
          <template #prepend>
            <AppMonogram :name="item.raw.title" :square="item.raw.kind === 'team'" :size="28" class="mr-3" />
          </template>
        </v-list-item>
      </template>
    </v-autocomplete>
    <v-select v-model="role" :items="roles" label="As" :disabled="disabled" density="compact" hide-details class="grant-add__role" />
    <v-btn type="submit" color="primary" height="40" :disabled="disabled || !picked" :loading="busy">Add</v-btn>
  </form>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AppMonogram from '@/components/common/AppMonogram.vue'
import type { GrantCandidate } from '@/composables/useMemberSettings'
import { BOARD_ROLES, ROLE_LABELS } from '@/constants/boards'
import type { BoardRole } from '@/types/boards'

const props = defineProps<{
  candidates: GrantCandidate[]
  withTeams: boolean
  disabled: boolean
  add: (candidate: GrantCandidate, role: BoardRole) => Promise<boolean>
}>()

const picked = ref<GrantCandidate | null>(null)
const role = ref<BoardRole>('editor')
const busy = ref(false)
const roles = BOARD_ROLES.map(value => ({ value, title: ROLE_LABELS[value] }))

/** Match the name, or the email (or "Team") under it. */
function matches(_value: string, query: string, item?: { raw: GrantCandidate }): boolean {
  const q = query.trim().toLowerCase()
  if (!q || !item) return true
  return `${item.raw.title} ${item.raw.subtitle}`.toLowerCase().includes(q)
}

async function submit(): Promise<void> {
  if (!picked.value) return
  busy.value = true
  const ok = await props.add(picked.value, role.value)
  busy.value = false
  if (ok) picked.value = null
}
</script>

<style scoped>
.grant-add {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 140px auto;
  gap: 12px;
  align-items: center;
}
@media (max-width: 600px) {
  .grant-add {
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .grant-add__who {
    grid-column: 1 / -1;
  }
}
</style>
