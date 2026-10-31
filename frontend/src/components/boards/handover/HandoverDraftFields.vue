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
     what that means for its agents), its priority (the card's, else P2),
     the repositories it starts with (remove any that don't apply) and its
     requirements. Edits here change only this handover. -->
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
      <AppPillToggle v-model="target" :options="HANDOVER_TARGETS" size="sm" :aria-labelledby="landsId" />
      <span class="handover-draft__note">{{ HANDOVER_TARGET_NOTES[target] }}</span>
      <span v-if="!hasRequirements" class="handover-draft__muted">Tech arch needs a PRD or a description on the card.</span>
    </div>
    <dl class="handover-draft__facts">
      <dt>Priority</dt>
      <dd>{{ priority }}</dd>
      <dt>Repositories</dt>
      <dd class="handover-draft__repos">
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
      </dd>
    </dl>
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

const landsId = useId()
const repos = computed(() =>
  (props.draft.preview.value?.impacted_repos ?? []).filter(r => props.draft.repoIds.value.includes(r.repo_id)),
)
const priority = computed(() => {
  const p = props.draft.preview.value?.priority ?? 'P2'
  return props.cardPriority ? `${p}, from the card` : `${p}, as the card has none`
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
  font-size: 12px;
}
.handover-draft__muted {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.handover-draft__facts {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: 8px 14px;
  margin: 0;
  font-size: 14px;
  align-content: start;
}
.handover-draft__facts dt {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.handover-draft__facts dd {
  margin: 0;
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
