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

<!-- A board's settings, inside the board route's shell (which has loaded
     the board, my role and what I may do). Admins edit; anyone else, and
     everyone while the board is archived, sees them read-only. General
     and Handover save with the Save button and ask before unsaved edits
     are left; the other sections save each change as it's made. -->
<template>
  <SettingsPageShell
    v-if="detail"
    title="Board settings"
    :subtitle="detail.board.name"
    :loading="false"
    :saving="status.saving.value"
    :valid="!!form && form.valid.value"
    :error="null"
    :save-success="false"
    :show-save="!!form && board.can('edit_settings')"
    :back-to="{ name: 'board', params: { key: detail.board.key } }"
    back-label="Back to the board"
    @save="save"
  >
    <template #header-actions>
      <span class="board-settings__status" role="status" aria-live="polite">{{ status.announcement.value }}</span>
    </template>
    <div class="board-settings">
      <BoardSettingsNav :board-key="detail.board.key" :section="section" />
      <div class="board-settings__main">
        <AppCallout v-if="board.archived.value" variant="warning" icon="mdi-archive-outline">
          This board is archived.
          {{ board.can('archive_board') ? 'Restore it to change its settings.' : 'Its settings can be read but not changed.' }}
        </AppCallout>
        <AppCallout v-else-if="!isAdmin" variant="info" icon="mdi-eye-outline" role="note">
          Only the board's admins can change its settings. {{ rolePhrase(detail.role) }}.
        </AppCallout>
        <AppCallout v-if="status.error.value" variant="error" role="alert">{{ status.error.value }}</AppCallout>
        <GeneralSection v-if="section === 'general'" :form="general" :board="detail.board" :limits="limits" :disabled="!board.can('edit_settings')" />
        <StagesSection v-else-if="section === 'stages'" :board="detail.board" :limits="limits" :status="status" :disabled="!board.can('manage_stages')" />
        <MembersSection
          v-else-if="section === 'members'"
          :visibility="detail.board.visibility"
          :status="status"
          :can-edit-members="board.can('manage_members')"
          :can-edit-visibility="board.can('edit_settings')"
        />
        <LabelsSection v-else-if="section === 'labels'" :limits="limits" :status="status" :disabled="!board.can('manage_labels')" />
        <HandoverSection v-else-if="section === 'handover'" :form="handover" :disabled="!board.can('edit_settings')" />
        <ArchiveSection
          v-else
          :board="detail.board"
          :archived="board.archived.value"
          :can-archive="board.can('archive_board')"
          :status="status"
        />
      </div>
    </div>
    <AppConfirmDialog
      :model-value="guard.asking.value"
      title="Leave without saving?"
      body="Your changes in this section haven't been saved."
      action="Leave"
      @update:model-value="open => !open && guard.answer(false)"
      @confirm="guard.answer(true)"
    />
  </SettingsPageShell>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import ArchiveSection from '@/components/boards/settings/ArchiveSection.vue'
import BoardSettingsNav from '@/components/boards/settings/BoardSettingsNav.vue'
import GeneralSection from '@/components/boards/settings/GeneralSection.vue'
import HandoverSection from '@/components/boards/settings/HandoverSection.vue'
import LabelsSection from '@/components/boards/settings/LabelsSection.vue'
import MembersSection from '@/components/boards/settings/MembersSection.vue'
import StagesSection from '@/components/boards/settings/StagesSection.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import SettingsPageShell from '@/components/settings/SettingsPageShell.vue'
import { useBoardContext } from '@/composables/useBoardContext'
import { useGeneralForm, useHandoverForm } from '@/composables/useBoardSettingsForms'
import { useBoardSettingsStatus } from '@/composables/useBoardSettingsStatus'
import { useUnsavedGuard } from '@/composables/useUnsavedGuard'
import { rolePhrase } from '@/constants/boards'
import { useBoardsStore } from '@/stores/boards'
import { SECTION_QUERY_KEY, sectionFrom } from '@/utils/boardSettingsSections'

const page = useBoardContext()
const { board } = page
const boards = useBoardsStore()
const route = useRoute()

const detail = computed(() => board.detail.value)
const limits = computed(() => boards.limits)
const isAdmin = computed(() => detail.value?.role === 'admin')
const section = computed(() => sectionFrom(route.query[SECTION_QUERY_KEY]))

const status = useBoardSettingsStatus(page)
const general = useGeneralForm(page, status, limits)
const handover = useHandoverForm(page, status)
const form = computed(() =>
  section.value === 'general' ? general : section.value === 'handover' ? handover : null,
)

// Another board's settings replace this one's too, so a new key asks as well.
const guard = useUnsavedGuard(
  computed(() => general.dirty.value || handover.dirty.value),
  [SECTION_QUERY_KEY],
  ['key'],
)

// Leaving a section (after the guard, when it had edits) drops its edits and its error.
watch(section, () => {
  general.reset()
  handover.reset()
  status.clearError()
})

onMounted(() => void boards.ensureLimits())

function save(): void {
  void form.value?.save()
}
</script>

<style scoped>
.board-settings {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 28px;
}
.board-settings__main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
.board-settings__status {
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (max-width: 960px) {
  .board-settings {
    grid-template-columns: minmax(0, 1fr);
    gap: 16px;
  }
}
@media (pointer: coarse) {
  .board-settings :deep(.v-btn),
  .board-settings :deep(.v-field) {
    min-height: 44px;
  }
}
</style>
