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

<!-- What a request would cost and who decides it, from the server's
     preview. Problems explain why it can't be sent yet. -->
<template>
  <div class="preview" aria-live="polite">
    <div v-if="previewing" class="d-flex align-center ga-2 preview__muted">
      <v-progress-circular indeterminate size="14" width="2" />
      Checking dates…
    </div>
    <AppCallout v-else-if="error" variant="error">{{ error }}</AppCallout>
    <template v-else-if="preview">
      <div class="preview__row">
        <span class="preview__label">Working days</span>
        <span class="preview__value">{{ daysLine }}</span>
      </div>
      <div v-if="balance" class="preview__row">
        <span class="preview__label">{{ typeName }} after this</span>
        <span class="preview__value">{{ balance }}</span>
      </div>
      <p v-if="approval" class="preview__approval">{{ approval }}.</p>
      <p v-if="skips" class="preview__note">{{ skips }}</p>
      <AppCallout v-if="lopLine" variant="warning">{{ lopLine }}</AppCallout>
      <AppCallout v-if="preview.high_leave" :variant="highLeaveVariant(preview.high_leave)">
        {{ highLeaveForSelf(preview.high_leave, true) }}
      </AppCallout>
      <AppCallout v-if="blocking.length" ref="problemsBox" variant="error">
        <div v-for="problem in blocking" :key="problem.code">{{ problem.message }}</div>
      </AppCallout>
      <AppCallout v-if="lopConfirm" ref="lopBox" variant="warning">
        <div>{{ lopConfirm.message }}</div>
        <v-checkbox
          :model-value="acceptLop"
          :label="`Apply ${lopDays} as loss of pay (unpaid)`"
          density="compact"
          hide-details
          @update:model-value="emit('update:acceptLop', !!$event)"
        />
      </AppCallout>
    </template>
    <div v-else class="preview__muted">{{ placeholder }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import type { LeaveKind, LeavePreview, PolicyBrief } from '@/types/leave'
import { highLeaveForSelf, highLeaveVariant } from '@/utils/highLeave'
import {
  approvalLine,
  excludedSummary,
  formatDays,
  lopLabel,
  pluralDays,
  toNumber,
  toNumberOrNull,
} from '@/utils/leave'

const props = defineProps<{
  preview: LeavePreview | null
  previewing: boolean
  error: string
  kind: LeaveKind
  policy: PolicyBrief | null
  /** Leave type name for the balance line. */
  typeName: string
  /** They ticked the loss-of-pay box. */
  acceptLop?: boolean
  placeholder: string
}>()
const emit = defineEmits<{ 'update:acceptLop': [value: boolean] }>()

// Days past the balance are asked about, not refused: they tick a box to agree.
const lopConfirm = computed(() => props.preview?.problems.find(p => p.code === 'lop_confirm'))
const blocking = computed(() => props.preview?.problems.filter(p => p.code !== 'lop_confirm') ?? [])
const lopDays = computed(() => pluralDays(toNumber(props.preview?.lop_days)))

// The reason a request can't be sent sits under the form's other fields; bring
// it into view so a disabled Send button never has a hidden explanation.
const problemsBox = ref<{ $el: HTMLElement } | null>(null)
const lopBox = ref<{ $el: HTMLElement } | null>(null)
watch(
  () => props.preview?.problems.map(p => p.message).join('|') ?? '',
  async text => {
    if (!text) return
    await nextTick()
    const box = problemsBox.value ?? lopBox.value
    box?.$el?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' })
  },
)

const daysLine = computed(() => {
  const days = toNumber(props.preview?.days)
  return `${formatDays(days)} ${days === 1 ? 'day' : 'days'}`
})

// "Skips Sat, Sun and Diwali", as a sentence under the numbers.
const skips = computed(() => {
  const text = props.preview ? excludedSummary(props.preview.excluded, props.policy?.working_days ?? []) : ''
  return text ? `${text[0].toUpperCase()}${text.slice(1)}.` : ''
})

// Days past the balance aren't refused: they're unpaid.
const lopLine = computed(() => {
  // A type that stops at its balance refuses instead: its message says what to do.
  if (props.preview?.problems.some(p => p.code === 'over_balance' || p.code === 'lop_confirm')) return ''
  const lop = lopLabel(props.preview?.lop_days)
  return lop ? `${lop}: these days are past your ${props.typeName ?? 'leave'} balance, so they're unpaid.` : ''
})

// "10 → 6 days left".
const balance = computed(() => {
  if (props.kind !== 'leave' || !props.preview) return ''
  const before = toNumberOrNull(props.preview.balance_before)
  const after = toNumberOrNull(props.preview.balance_after)
  if (before === null || after === null) return ''
  return `${formatDays(before)} → ${formatDays(after)} ${after === 1 ? 'day' : 'days'} left`
})

const approval = computed(() =>
  props.preview ? approvalLine(props.preview, props.kind, props.policy?.wfh_approval ?? null) : '',
)
</script>

<style scoped>
.preview {
  padding: 14px 16px;
  border-radius: 10px;
  background: rgb(var(--v-theme-surface-variant));
  min-height: 48px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: var(--text-sm);
}
.preview__row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}
.preview__label {
  color: rgb(var(--v-theme-ink-2));
}
.preview__value {
  font-weight: 600;
  text-align: right;
}
.preview__approval {
  margin: 0;
  color: rgb(var(--v-theme-ink-2));
}
.preview__note,
.preview__muted {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
