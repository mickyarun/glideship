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

<!-- "Send BUD-140 back to PDT-17?": says what happens (the BUD is
     discarded, the card goes back with my reason, and a later handover
     brings the same BUD back), asks for the reason (required; a common
     one is a tap away), and sends it. A refusal stays here in its code's
     words. -->
<template>
  <AppConfirmDialog
    :model-value="modelValue"
    :title="`Send ${budKey} back to ${cardKey}?`"
    action="Discard BUD and send back"
    color="error"
    :busy="busy"
    :disabled="!reason.trim()"
    @update:model-value="open => !open && emit('update:modelValue', false)"
    @confirm="submit"
  >
    <template #body>
      {{ budKey }} is discarded. {{ cardKey }} goes back on the {{ boardName }} board, and its assignees see your
      reason. If it's handed over again, {{ budKey }} comes back with the same number.
    </template>
    <div class="send-back__quick" role="group" aria-label="Common reasons">
      <v-chip v-for="r in SEND_BACK_REASONS" :key="r" tag="button" type="button" size="small" variant="outlined" @click="start(r)">{{ r }}</v-chip>
    </div>
    <v-textarea
      ref="field"
      v-model="reason"
      label="Reason (required)"
      rows="3"
      auto-grow
      :maxlength="SEND_BACK_REASON_MAX"
      hide-details="auto"
    />
    <AppCallout v-if="failure" variant="error" role="alert">{{ failure }}</AppCallout>
  </AppConfirmDialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { SEND_BACK_REASON_MAX, SEND_BACK_REASONS } from '@/constants/boards'
import { useBudOriginStore } from '@/stores/budOrigin'

const props = defineProps<{ modelValue: boolean; budKey: string; cardKey: string; boardName: string }>()
const emit = defineEmits<{ 'update:modelValue': [open: boolean]; sent: [] }>()

const store = useBudOriginStore()
const reason = ref('')
const busy = ref(false)
const failure = ref('')
const field = ref<{ focus: () => void } | null>(null)

watch(() => props.modelValue, open => {
  if (!open) return
  reason.value = ''
  failure.value = ''
})

/** A common reason starts the text (whatever I'd written stays after it), and I carry on typing. */
function start(r: string): void {
  const rest = reason.value.trim()
  reason.value = rest ? `${r}: ${rest}` : `${r}: `
  field.value?.focus()
}

async function submit(): Promise<void> {
  const text = reason.value.trim()
  if (!text || busy.value) return
  busy.value = true
  failure.value = ''
  const refused = await store.sendBack(text)
  busy.value = false
  if (refused) {
    failure.value = refused.text
    return
  }
  emit('sent')
  emit('update:modelValue', false)
}
</script>

<style scoped>
.send-back__quick {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
