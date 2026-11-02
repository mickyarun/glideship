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

<!-- Members and visibility: who can see the board, then the people and
     teams holding a role on it. Each change saves as it's made; making the
     board members-only, removing someone and lowering my own admin role
     ask first. -->
<template>
  <div class="members">
    <AppPanel title="Visibility">
      <BoardVisibilityField
        :model-value="visibility"
        legend="Who can see this board"
        :disabled="!canEditVisibility"
        @update:model-value="pickVisibility"
      />
    </AppPanel>
    <AppPanel title="Members" note="If someone is in two places, their highest role wins.">
      <GrantAddForm
        v-if="canEditMembers"
        :candidates="members.candidates.value"
        :with-teams="members.canListTeams.value"
        :disabled="false"
        :add="members.add"
      />
      <AppCallout v-if="members.loadError.value" variant="error" role="alert" class="mt-4">
        {{ members.loadError.value }}
        <template #actions>
          <v-btn variant="outlined" size="small" @click="members.load()">Try again</v-btn>
        </template>
      </AppCallout>
      <ul v-if="members.rows.value.length" class="members__list" aria-label="People and teams with a role">
        <GrantRow
          v-for="grant in members.rows.value"
          :key="`${grant.kind}:${grant.id}`"
          :grant="grant"
          :last="isLast(grant)"
          :disabled="!canEditMembers"
          @role="role => pickRole(grant, role)"
          @remove="askRemove(grant)"
        />
      </ul>
      <AppEmptyState
        v-else-if="!members.loading.value && !members.loadError.value"
        icon="mdi-account-multiple-outline"
        title="No one has a role of their own yet"
        body="Add people or teams to let them edit this board."
      />
      <p v-if="members.lastAdmin.value" class="members__note">
        {{ members.lastAdmin.value.name }} is the only admin and can't be removed until there's another admin.
      </p>
    </AppPanel>
    <AppConfirmDialog
      v-model="removeOpen"
      :title="removeTitle"
      :body="removeBody"
      :action="removing?.kind === 'team' ? 'Remove team' : 'Remove'"
      color="error"
      :busy="status.saving.value"
      @confirm="confirmRemove"
    />
    <AppConfirmDialog
      :model-value="!!asking"
      :title="asking?.title ?? ''"
      :body="asking?.body ?? ''"
      :action="asking?.action ?? ''"
      :color="asking?.color ?? 'primary'"
      @update:model-value="open => !open && (asking = null)"
      @confirm="confirmAsk"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import BoardVisibilityField from '@/components/boards/BoardVisibilityField.vue'
import GrantAddForm from '@/components/boards/settings/GrantAddForm.vue'
import GrantRow from '@/components/boards/settings/GrantRow.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AppEmptyState from '@/components/common/AppEmptyState.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { useBoardContext } from '@/composables/useBoardContext'
import type { BoardSettingsStatus } from '@/composables/useBoardSettingsStatus'
import { useMemberConfirms } from '@/composables/useMemberConfirms'
import { useMemberSettings, type Grant } from '@/composables/useMemberSettings'
import type { BoardVisibility } from '@/types/boards'

const props = defineProps<{
  visibility: BoardVisibility
  status: BoardSettingsStatus
  canEditMembers: boolean
  canEditVisibility: boolean
}>()

const page = useBoardContext()
const members = useMemberSettings(page, props.status)
const { asking, pickVisibility, pickRole, confirmAsk } = useMemberConfirms(page, members, () => props.visibility)
const removing = ref<Grant | null>(null)
const removeOpen = computed({
  get: () => removing.value !== null,
  set: open => {
    if (!open) removing.value = null
  },
})

// "Remove the Design team?", whether or not the team's name ends in "team".
const removeTitle = computed(() => {
  const grant = removing.value
  if (grant?.kind !== 'team') return `Remove ${grant?.name ?? ''}?`
  return `Remove the ${grant.name}${/\bteam$/i.test(grant.name) ? '' : ' team'}?`
})

const removeBody = computed(() =>
  removing.value?.kind === 'team'
    ? "Its members lose the role this team gives them. Anyone with a role of their own, or from another team, keeps it."
    : 'They lose the role they have of their own. A role they get from a team still applies.',
)

function isLast(grant: Grant): boolean {
  const last = members.lastAdmin.value
  return !!last && last.kind === grant.kind && last.id === grant.id
}

function askRemove(grant: Grant): void {
  props.status.clearError()
  removing.value = grant
}

async function confirmRemove(): Promise<void> {
  const grant = removing.value
  removing.value = null
  if (grant) await members.remove(grant)
}
</script>

<style scoped>
.members {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.members__list {
  margin: 16px 0 0;
  padding: 0;
  list-style: none;
}
.members__note {
  margin: 12px 0 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
