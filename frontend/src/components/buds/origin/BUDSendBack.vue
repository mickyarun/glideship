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

<!-- Sending a BUD that came from a card back to it, asked for from the
     header's menu (useBudSendBack decides when it's offered). Once sent,
     the BUD (now discarded) and its history reload, and a note says where
     it went. -->
<template>
  <AppCallout v-if="sentTo" variant="success">
    Sent back to {{ sentTo }}. The card's assignees see your reason.
    <template #actions>
      <v-btn icon="mdi-close" variant="text" size="small" aria-label="Dismiss" @click="sentTo = ''" />
    </template>
  </AppCallout>
  <BUDSendBackDialog
    v-if="card" v-model="store.asking" :bud-key="budKey" :card-key="card.key" :board-name="card.board.name" @sent="sent"
  />
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BUDSendBackDialog from '@/components/buds/origin/BUDSendBackDialog.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import { useBudSendBack } from '@/composables/useBudSendBack'
import { useBUDStore } from '@/stores/bud'
import { useBudOriginStore } from '@/stores/budOrigin'
import { budRef, type BUDDocument } from '@/types'

const props = defineProps<{ bud: BUDDocument }>()
const emit = defineEmits<{ sent: [] }>()

const store = useBudOriginStore()
const budStore = useBUDStore()
const { card } = useBudSendBack(() => props.bud)
const sentTo = ref('')

const budKey = computed(() => budRef(props.bud.bud_number))

// The page is reused for the next BUD: nothing of this one's send-back carries over.
watch(() => props.bud.id, () => {
  sentTo.value = ''
  store.asking = false
})

async function sent(): Promise<void> {
  sentTo.value = card.value?.key ?? 'the board'
  await budStore.refreshBUDIfCurrent(props.bud.id)
  emit('sent')
}
</script>
