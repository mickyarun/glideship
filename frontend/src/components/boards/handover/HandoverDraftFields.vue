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

<!-- The new BUD as a create would make it: its title, where it lands (and
     what that means for its agents; Tech arch needs a PRD or a description
     on the card), its priority (the card's, else P2), the repositories it
     starts with (remove any that don't apply) and its requirements. Edits
     here change only this handover. A landing whose preview failed says so
     under the choice, so another can be picked. -->
<template>
  <div class="handover-draft">
    <v-text-field
      v-model="draft.title.value"
      label="BUD title"
      hide-details="auto"
      :rules="[v => !!v?.trim() || 'The BUD needs a title.']"
      class="handover-draft__wide"
    />
    <div class="handover-draft__field">
      <span :id="landsId" class="handover-draft__label">Lands at</span>
      <AppPillToggle v-model="target" :options="targets" size="sm" :aria-labelledby="landsId" :aria-describedby="landsNoteId" />
      <span :id="landsNoteId" class="handover-draft__note">
        {{ HANDOVER_TARGET_NOTES[target] }}
        <span v-if="!hasRequirements" class="handover-draft__muted">{{ NEEDS_REQUIREMENTS }}</span>
      </span>
      <span v-if="draft.failure.value" class="handover-draft__error" role="alert">{{ draft.failure.value.text }}</span>
    </div>
    <div class="handover-draft__field">
      <span :id="priorityId" class="handover-draft__label">Priority</span>
      <AppPillToggle v-model="draft.priority.value" :options="PRIORITIES" size="sm" :aria-labelledby="priorityId" />
      <span class="handover-draft__muted">{{ priorityNote }}</span>
    </div>
    <div class="handover-draft__field handover-draft__wide">
      <span class="handover-draft__label">Repositories</span>
      <div class="handover-draft__repos">
        <v-chip
          v-for="repo in repos"
          :key="repo.repo_id"
          size="small"
          closable
          :close-label="`Leave out ${repo.repo_name}`"
          @click:close="draft.repoIds.value = draft.repoIds.value.filter(id => id !== repo.repo_id)"
        >
          {{ repo.repo_name }}
        </v-chip>
        <span v-if="!repos.length" class="handover-draft__muted">None: add them on the BUD later.</span>
      </div>
    </div>
    <HandoverRequirements
      v-model="draft.requirements.value"
      :original="draft.preview.value?.requirements_md ?? ''"
      :has-prd="hasPrd"
      :max-length="docMax"
      class="handover-draft__wide"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, useId } from 'vue'
import HandoverRequirements from '@/components/boards/handover/HandoverRequirements.vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import type { HandoverPreviewState } from '@/composables/useHandoverPreview'
import { HANDOVER_TARGET_NOTES, HANDOVER_TARGETS } from '@/constants/boards'
import { BUD_PRIORITIES } from '@/types'
import type { HandoverTarget } from '@/types/boards/settings'

const props = defineProps<{
  draft: HandoverPreviewState
  /** The card's own priority, if it has one. */
  cardPriority: string | null
  hasPrd: boolean
  hasRequirements: boolean
  docMax: number | null
}>()
const target = defineModel<HandoverTarget>('target', { required: true })

const NEEDS_REQUIREMENTS = 'Tech arch needs a PRD or a description on the card.'
const PRIORITIES = BUD_PRIORITIES.map(p => ({ label: p, value: p }))
const landsId = useId()
const landsNoteId = useId()
const priorityId = useId()
// Tech arch plans from the requirements, so it waits for the card to have some.
const targets = computed(() =>
  HANDOVER_TARGETS.map(t => ({ ...t, disabled: t.value === 'tech_arch' && !props.hasRequirements })),
)
const repos = computed(() =>
  (props.draft.preview.value?.impacted_repos ?? []).filter(r => props.draft.repoIds.value.includes(r.repo_id)),
)
const priorityNote = computed(() => {
  const from = props.draft.preview.value?.priority ?? 'P2'
  if (props.draft.priorityChange.value) return `Changed from ${from} for this BUD.`
  return props.cardPriority ? 'From the card.' : 'The card has none, so P2.'
})
</script>

<style scoped>
.handover-draft {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.handover-draft__wide {
  grid-column: 1 / -1;
}
.handover-draft__field {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
.handover-draft__label {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.handover-draft__note {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
}
.handover-draft__muted {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.handover-draft__error {
  font-size: 12px;
  color: rgb(var(--v-theme-error));
}
.handover-draft__repos {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
@media (max-width: 600px) {
  .handover-draft {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
