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

<!-- One dialog for every goal form: adding, editing, suggesting a change,
     and the reason-only ones (asking for a rewording, declining). -->
<template>
  <v-dialog :model-value="mode !== null" max-width="560" @update:model-value="v => !v && emit('close')">
    <v-card v-if="mode">
      <v-card-title>{{ TEXT[mode].title }}</v-card-title>
      <v-card-text class="goal-dialog">
        <template v-if="TEXT[mode].words">
          <p class="goal-dialog__hint">An outcome, not a task list, and how you'll know you got there.</p>
          <v-text-field v-model="title" label="Goal" maxlength="200" autofocus />
          <v-text-field v-model="measure" label="How you'll know (a number or a clear yes or no, and where it comes from)" maxlength="300" />
        </template>
        <v-textarea
          v-if="TEXT[mode].reason"
          v-model="reason"
          :label="TEXT[mode].reason"
          rows="2"
          auto-grow
          maxlength="300"
        />
        <AppCallout v-if="error" variant="error">{{ error }}</AppCallout>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="emit('close')">Cancel</v-btn>
        <v-btn color="primary" :disabled="!ready" :loading="busy" @click="submit">{{ TEXT[mode].action }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import type { GoalBody } from '@/types/appraisalGoals'
import type { GoalDialogMode } from '@/utils/appraisalGoals'

interface ModeText {
  title: string
  action: string
  words: boolean
  reason?: string
  needsReason?: boolean
}

const TEXT: Record<GoalDialogMode, ModeText> = {
  propose: { title: 'Add my own goal', action: 'Send to my manager', words: true },
  add: { title: 'Add a goal', action: 'Add goal', words: true, reason: 'Why now (they see this)', needsReason: true },
  edit: { title: 'Edit the goal', action: 'Save', words: true },
  'edit-reason': { title: 'Change the goal', action: 'Save change', words: true, reason: 'Why it changed (they see this)', needsReason: true },
  'suggest-change': { title: 'Suggest a change', action: 'Send to my manager', words: true, reason: 'Why (optional)' },
  reword: { title: 'Ask to reword', action: 'Send back', words: false, reason: 'What to change (they see this)', needsReason: true },
  decline: { title: 'Not this period', action: 'Not adding it', words: false, reason: 'Why (they see this)', needsReason: true },
}

const props = defineProps<{ mode: GoalDialogMode | null; start?: Partial<GoalBody>; busy: boolean; error: string }>()
const emit = defineEmits<{ close: []; submit: [body: GoalBody] }>()

const title = ref('')
const measure = ref('')
const reason = ref('')

watch(
  () => props.mode,
  () => {
    title.value = props.start?.title ?? ''
    measure.value = props.start?.measure ?? ''
    reason.value = ''
  },
)

const ready = computed(() => {
  const mode = props.mode
  if (!mode) return false
  if (TEXT[mode].words && !title.value.trim()) return false
  return !TEXT[mode].needsReason || Boolean(reason.value.trim())
})

function submit(): void {
  emit('submit', {
    title: title.value.trim(),
    measure: measure.value.trim(),
    reason: reason.value.trim(),
    source: props.start?.source ?? null,
  })
}
</script>

<style scoped>
.goal-dialog {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.goal-dialog__hint {
  margin: 0;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
