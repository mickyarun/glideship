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

<!-- One BUD a card was handed over to: its key (a link, with its title,
     when I may open it; plain text otherwise, never the title), its
     status, and what happened to it: sent back with the reason, discarded
     on the Delivery board, or its stage's agents not started (with Retry
     for whoever may hand over). -->
<template>
  <li class="handover-row" :class="{ 'handover-row--off': off }">
    <div class="handover-row__line">
      <router-link v-if="link" :to="link" class="handover-row__key">{{ handover.bud_key }}</router-link>
      <span v-else class="handover-row__key">{{ handover.bud_key ?? 'Deleted BUD' }}</span>
      <span v-if="title" class="handover-row__title">{{ title }}</span>
      <AppTag :color="statusColor(handover.bud_status, returned)" sr-prefix="Status">{{ status }}</AppTag>
    </div>
    <p v-if="returned" class="handover-row__note">
      Sent back {{ when(handover.returned_at) }}<template v-if="handover.return_reason">: “{{ handover.return_reason }}”</template>
    </p>
    <p v-else-if="handover.bud_status === 'discarded'" class="handover-row__note">
      Discarded on the Delivery board. It can be restored there.
    </p>
    <p v-if="stuck" class="handover-row__note handover-row__note--warn">
      Couldn't start {{ stageName }} agents
      <template v-if="canRetry">
        · <button type="button" class="handover-row__retry" :disabled="retrying" @click="emit('retry', handover)">Retry</button>
      </template>
    </p>
  </li>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppTag from '@/components/common/AppTag.vue'
import { useBudAccess } from '@/composables/useBudAccess'
import { HANDOVER_TARGETS } from '@/constants/boards'
import type { HandoverRead } from '@/types/boards'
import { formatDate } from '@/utils/date'
import { statusColor, statusLabel } from '@/utils/handoverChips'

const props = defineProps<{ handover: HandoverRead; canRetry: boolean; retrying: boolean }>()
const emit = defineEmits<{ retry: [handover: HandoverRead] }>()

const { canOpen, titleOf } = useBudAccess()
const returned = computed(() => props.handover.status === 'returned')
const off = computed(() => returned.value || props.handover.bud_status === 'discarded')
const link = computed(() => (canOpen(props.handover) ? `/buds/${props.handover.bud_id}` : null))
const title = computed(() => titleOf(props.handover))
const status = computed(() => (returned.value ? 'Returned' : statusLabel(props.handover.bud_status)))
const stuck = computed(() => !returned.value && !!props.handover.stage_start_failed)
const stageName = computed(() => {
  const target = props.handover.target_status ?? props.handover.bud_status
  return HANDOVER_TARGETS.find(t => t.value === target)?.label ?? statusLabel(target)
})

const when = (iso: string | null) => (iso ? `on ${formatDate(iso)}` : '')
</script>

<style scoped>
.handover-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid rgb(var(--v-theme-rule));
  background: rgb(var(--v-theme-background));
}
.handover-row__line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.handover-row__key {
  font: 500 12px var(--font-mono);
  color: rgb(var(--v-theme-on-surface-variant));
}
a.handover-row__key {
  color: rgb(var(--v-theme-primary));
}
.handover-row__title {
  flex: 1 1 140px;
  min-width: 0;
  font-size: 13px;
  overflow-wrap: anywhere;
}
.handover-row--off .handover-row__key,
.handover-row--off .handover-row__title {
  text-decoration: line-through;
}
.handover-row__note {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
  overflow-wrap: anywhere;
}
.handover-row__note--warn {
  color: rgb(var(--v-theme-warning));
}
.handover-row__retry {
  border: 0;
  padding: 0;
  background: none;
  color: rgb(var(--v-theme-primary));
  font: inherit;
  text-decoration: underline;
  cursor: pointer;
}
.handover-row__retry:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
</style>
