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

<!-- "Send back to <board>" on a BUD that came from a card, while it's
     still in requirements, design or tech arch and the card still holds
     it, for whoever may edit BUDs. Once sent, the BUD (now discarded) and
     its history reload, and a note says where it went. -->
<template>
  <AppCallout v-if="sentTo" variant="success">
    Sent back to {{ sentTo }}. The card's assignees see your reason.
    <template #actions>
      <v-btn icon="mdi-close" variant="text" size="small" aria-label="Dismiss" @click="sentTo = ''" />
    </template>
  </AppCallout>
  <AppCallout v-else-if="card && offered" variant="info" icon="mdi-keyboard-return">
    {{ budKey }} came from {{ card.key }} on the {{ card.board.name }} board. If it isn't ready to build, send it back.
    <template #actions>
      <v-btn variant="outlined" size="small" @click="open = true">Send back to {{ card.board.name }}…</v-btn>
    </template>
  </AppCallout>
  <BUDSendBackDialog
    v-if="card" v-model="open" :bud-key="budKey" :card-key="card.key" :board-name="card.board.name" @sent="sent"
  />
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BUDSendBackDialog from '@/components/buds/origin/BUDSendBackDialog.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import { usePermissions } from '@/composables/usePermissions'
import { useBUDStore } from '@/stores/bud'
import { useBudOriginStore } from '@/stores/budOrigin'
import { budRef, type BUDDocument } from '@/types'
import { canSendBack } from '@/utils/handoverChips'

const props = defineProps<{ bud: BUDDocument }>()
const emit = defineEmits<{ sent: [] }>()

const store = useBudOriginStore()
const budStore = useBUDStore()
const { hasPermission } = usePermissions()
const open = ref(false)
const sentTo = ref('')

const budKey = computed(() => budRef(props.bud.bud_number))
const card = computed(() => (store.budId === props.bud.id ? store.origin?.card ?? null : null))
const offered = computed(() => !!store.active && canSendBack(props.bud.status) && hasPermission('buds:edit'))

// The page is reused for the next BUD: nothing of this one's send-back carries over.
watch(() => props.bud.id, () => {
  sentTo.value = ''
  open.value = false
})

async function sent(): Promise<void> {
  sentTo.value = card.value?.key ?? 'the board'
  await budStore.refreshBUDIfCurrent(props.bud.id)
  emit('sent')
}
</script>
