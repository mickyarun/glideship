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

<!-- A person or team holding a role on the board: change the role or take
     it away. The board's last admin can't be lowered or removed. -->
<template>
  <li class="grant-row">
    <AppMonogram :name="grant.name" :src="grant.avatarUrl" :square="grant.kind === 'team'" :size="32" />
    <div class="grant-row__who">
      <span class="grant-row__name">{{ grant.name }}</span>
      <span class="grant-row__meta">{{ meta }}</span>
    </div>
    <v-select
      :model-value="grant.role"
      :items="roles"
      :aria-label="`Role for ${grant.name}`"
      :disabled="disabled || last"
      density="compact"
      hide-details
      class="grant-row__role"
      @update:model-value="emit('role', $event)"
    />
    <v-btn variant="text" :disabled="disabled || last" :aria-label="`Remove ${grant.name}`" @click="emit('remove')">
      Remove
    </v-btn>
  </li>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppMonogram from '@/components/common/AppMonogram.vue'
import type { Grant } from '@/composables/useMemberSettings'
import { BOARD_ROLES, ROLE_LABELS } from '@/constants/boards'
import type { BoardRole } from '@/types/boards'

const props = defineProps<{ grant: Grant; last: boolean; disabled: boolean }>()
const emit = defineEmits<{ role: [role: BoardRole]; remove: [] }>()

const roles = BOARD_ROLES.map(value => ({ value, title: ROLE_LABELS[value] }))
const meta = computed(() => {
  const kind = props.grant.kind === 'team' ? 'Team' : 'Person'
  return props.last ? `${kind} · only admin` : kind
})
</script>

<style scoped>
.grant-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) 140px auto;
  gap: 12px;
  align-items: center;
  padding: 10px 0;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.grant-row__who {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.grant-row__name {
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.grant-row__meta {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (max-width: 600px) {
  .grant-row {
    grid-template-columns: auto minmax(0, 1fr) auto;
  }
  .grant-row__role {
    grid-column: 2 / 3;
  }
}
</style>
