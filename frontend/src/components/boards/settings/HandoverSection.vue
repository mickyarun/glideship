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

<!-- Handover to Delivery: whether cards can be handed over, the Done stage
     handed-over cards move to, the To do stage sent-back cards return to,
     and where new BUDs land by default. Saved with the page's Save button;
     the stage choices wait until handover is on. Anyone but an admin reads
     the settings as text. -->
<template>
  <AppPanel title="Handover to Delivery">
    <DraftConflictNote :show="form.conflict.value" class="mb-4" @reload="form.reset()" />
    <dl v-if="draft && disabled" class="handover__facts">
      <dt>Handover</dt>
      <dd>{{ draft.enabled ? 'On: cards can be handed over to Delivery' : 'Off' }}</dd>
      <dt>Handed-over cards move to</dt>
      <dd>{{ stageName(draft.stageId) }}</dd>
      <dt>Sent-back cards return to</dt>
      <dd>{{ stageName(draft.returnId) }}</dd>
      <dt>New BUDs land at</dt>
      <dd>{{ targetName }}</dd>
    </dl>
    <div v-else-if="draft" class="handover">
      <v-switch v-model="draft.enabled" color="primary" inset hide-details label="Cards on this board can be handed over to Delivery" />
      <AppCallout v-if="!form.doneStages.value.length" variant="info">Add a Done stage under Stages first.</AppCallout>
      <v-select
        v-model="draft.stageId"
        :items="stageItems(form.doneStages.value)"
        label="Handed-over cards move to"
        hint="Only Done stages are offered."
        persistent-hint
        clearable
        :error-messages="form.stageError.value || undefined"
        :disabled="!draft.enabled || !form.doneStages.value.length"
      />
      <v-select
        v-model="draft.returnId"
        :items="stageItems(form.todoStages.value)"
        label="Sent-back cards return to"
        hint="Only To do stages are offered."
        persistent-hint
        clearable
        :disabled="!draft.enabled"
      />
      <div class="handover__target">
        <span :id="targetLabel" class="handover__label">New BUDs land at, by default</span>
        <AppPillToggle
          v-model="draft.target"
          :options="HANDOVER_TARGETS"
          :aria-labelledby="targetLabel"
          :class="{ 'handover__pills--off': !draft.enabled }"
          :inert="!draft.enabled || undefined"
        />
        <span class="handover__note">Whoever hands a card over can change it each time.</span>
      </div>
    </div>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed, useId } from 'vue'
import DraftConflictNote from '@/components/boards/settings/DraftConflictNote.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import type { useHandoverForm } from '@/composables/useBoardSettingsForms'
import { CATEGORY_LABELS, HANDOVER_TARGETS } from '@/constants/boards'
import type { StageRead } from '@/types/boards'

const props = defineProps<{ form: ReturnType<typeof useHandoverForm>; disabled: boolean }>()

const draft = computed(() => props.form.draft.value)
const targetLabel = useId()
const targetName = computed(() => HANDOVER_TARGETS.find(t => t.value === draft.value?.target)?.label ?? '')

function stageItems(stages: StageRead[]) {
  return stages.map(s => ({ value: s.id, title: `${s.name} (${CATEGORY_LABELS[s.category]})` }))
}

function stageName(id: string | null): string {
  return [...props.form.doneStages.value, ...props.form.todoStages.value].find(s => s.id === id)?.name ?? 'Not set'
}
</script>

<style scoped>
.handover {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 560px;
}
.handover__facts {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: 10px 20px;
  margin: 0;
  font-size: 14px;
}
.handover__facts dt {
  color: rgb(var(--v-theme-on-surface-variant));
}
.handover__facts dd {
  margin: 0;
}
.handover__target {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
.handover__label {
  font-size: 13px;
  font-weight: 600;
}
.handover__note {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.handover__pills--off {
  opacity: 0.5;
}
</style>
