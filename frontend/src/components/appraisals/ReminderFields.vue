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

<!-- The reminder schedule: offsets in working days from each due date, the
     overdue nudge and HR's overdue list, with the DMs it produces. -->
<template>
  <div class="reminders">
    <v-text-field
      :model-value="offsetText"
      label="Reminder days"
      hint="Working days from the due date, comma-separated: -3 is three days before, 2 is two after."
      persistent-hint
      :error-messages="offsetError"
      @update:model-value="setOffsets"
    />
    <div class="reminders__switches">
      <v-switch
        :model-value="overdueNudge"
        label="Nudge after the due date"
        color="primary"
        hide-details
        @update:model-value="v => emit('update:overdueNudge', Boolean(v))"
      />
      <v-switch
        :model-value="hrList"
        label="Send HR a list of overdue feedback"
        color="primary"
        hide-details
        @update:model-value="v => emit('update:hrList', Boolean(v))"
      />
      <v-text-field
        v-if="hrList"
        :model-value="hrOffset"
        type="number"
        min="0"
        max="30"
        label="HR list, working days after"
        density="compact"
        hide-details
        @update:model-value="v => emit('update:hrOffset', Number(v))"
      />
    </div>
    <ReminderPreview :rows="preview" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ReminderPreview from '@/components/appraisals/ReminderPreview.vue'
import { dmPreview, parseOffsets } from '@/utils/appraisalSetup'

const props = defineProps<{ offsets: number[]; overdueNudge: boolean; hrList: boolean; hrOffset: number }>()
const emit = defineEmits<{
  'update:offsets': [value: number[]]
  'update:overdueNudge': [value: boolean]
  'update:hrList': [value: boolean]
  'update:hrOffset': [value: number]
}>()

const offsetText = ref(props.offsets.join(', '))
const offsetError = ref('')
watch(
  () => props.offsets,
  value => {
    if (parseOffsets(offsetText.value)?.join() !== value.join()) offsetText.value = value.join(', ')
  },
)

function setOffsets(text: string): void {
  offsetText.value = text
  const parsed = parseOffsets(text)
  offsetError.value = parsed ? '' : 'Use up to six whole numbers from -10 to 10.'
  if (parsed) emit('update:offsets', parsed)
}

const preview = computed(() => dmPreview(props.offsets, props.overdueNudge, props.hrList, props.hrOffset))
</script>

<style scoped>
.reminders {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.reminders__switches {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 24px;
}
.reminders__switches .v-text-field {
  max-width: 220px;
}
</style>
