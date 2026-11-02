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

<!-- A card's Delivery panel: the BUDs it was handed over to (oldest first,
     each with its history), "Hand over to Delivery" (then "Hand over
     another") when the server says I may, and a note that the card's later
     edits don't reach the BUDs. Shown while the board hands cards over, and
     for a card that holds handovers even after the board stops, so their
     history stays. The dialog outlives the panel while it's open, so a
     confirm in flight isn't lost. The board's card menu opens the dialog
     with ``?handover=1``. -->
<template>
  <AppPanel v-if="shown" title="Delivery">
    <template v-if="rollup" #action><span class="handover-panel__rollup">{{ rollup }}</span></template>
    <div class="handover-panel">
      <AppCallout v-if="list.error.value" variant="error">{{ list.error.value }}</AppCallout>
      <ul v-if="list.items.value.length" class="handover-panel__list" aria-label="Handed over to">
        <HandoverBudRow
          v-for="h in list.items.value" :key="h.id" :handover="h" :can-retry="canRetry"
          :retrying="list.retrying.value === h.id" @retry="retry"
        />
      </ul>
      <p v-else-if="list.loaded.value" class="handover-panel__text">{{ emptyText }}</p>
      <v-btn
        v-if="canHandOver"
        :variant="live.length ? 'outlined' : 'flat'" color="primary" class="handover-panel__cta" @click="open = true"
      >
        {{ ctaLabel }}
      </v-btn>
      <p v-if="list.items.value.length" class="handover-panel__text">
        Edits here don't reach the BUDs. Discuss delivery on the BUD.
      </p>
    </div>
  </AppPanel>
  <HandoverDialog
    v-if="detail && (shown || open)"
    v-model="open" :card="detail" :board="board" :holds-live="live.length > 0" :held-bud-ids="heldIds"
    :can-link="hasPermission('buds:edit')" :doc-max="docMax" @done="done" @fix="fix" @failed="reread"
  />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import HandoverBudRow from '@/components/boards/handover/HandoverBudRow.vue'
import HandoverDialog from '@/components/boards/handover/HandoverDialog.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { BoardCard } from '@/composables/useBoardCard'
import type { useBoardFeedback } from '@/composables/useBoardFeedback'
import { useBudAccess } from '@/composables/useBudAccess'
import { useCardHandovers } from '@/composables/useCardHandovers'
import { useHandoverOutcome } from '@/composables/useHandoverOutcome'
import { useHandoverQuery } from '@/composables/useHandoverQuery'
import { usePermissions } from '@/composables/usePermissions'
import type { BoardDetail, HandoverRead, HandoverResult, StageRequiredField } from '@/types/boards'
import { ENTER_QUERY_KEY, FOCUS_QUERY_KEY } from '@/utils/cardFocus'
import { deliveryRollup, isLive } from '@/utils/handoverChips'

const props = defineProps<{
  card: BoardCard
  board: BoardDetail
  feedback: ReturnType<typeof useBoardFeedback>
  docMax: number | null
}>()

const route = useRoute()
const router = useRouter()
const { hasPermission } = usePermissions()
const { mayHandOver } = useBudAccess()
const outcome = useHandoverOutcome(() => props.feedback)
const detail = computed(() => props.card.detail.value)
const enabled = computed(() => props.board.board.handover_enabled)
// Read the handovers while the board hands over, or while the card holds some.
const list = useCardHandovers(() => {
  const d = detail.value
  return d && (enabled.value || d.handovers.length) ? { id: d.id, key: d.key, number: d.number } : null
})
const open = ref(false)
const shown = computed(() => enabled.value || !!detail.value?.handovers.length || list.items.value.length > 0)

const live = computed(() => list.items.value.filter(isLive))
const heldIds = computed(() => list.items.value.flatMap(h => (h.bud_id && h.status === 'active' ? [h.bud_id] : [])))
// "1 of 2 in prod" once there are several, or the server says every one is in.
const rollup = computed(() => {
  const card = detail.value
  if (!card || (live.value.length < 2 && card.delivery !== 'delivered')) return null
  return deliveryRollup(card.handovers)
})
const canHandOver = computed(() => enabled.value && list.canHandOver.value)
const canRetry = computed(() => props.board.capabilities.includes('hand_over') && mayHandOver())
const emptyText = computed(() =>
  list.canHandOver.value
    ? 'When this is ready to build, hand it over. It becomes a BUD on the Delivery board, and this card tracks its progress.'
    : 'Not handed over yet. Handing over needs edit access here, engineering access and permission to create BUDs.',
)
const ctaLabel = computed(() => {
  if (live.value.length) return 'Hand over another'
  const last = list.items.value.at(-1)
  if (last?.status === 'returned' && last.bud_status === 'discarded') return `Hand over again (brings back ${last.bud_key})`
  return 'Hand over to Delivery'
})

useHandoverQuery({
  shown: () => shown.value,
  loaded: list.loaded,
  allowed: () => canHandOver.value,
  cardKey: () => detail.value?.key ?? '',
  open: () => (open.value = true),
  feedback: () => props.feedback,
})

function done(result: HandoverResult): void {
  list.added(result.handover)
  props.card.detail.value = result.card
  outcome.handedOver(result)
}

/** A confirm that failed may still have committed: read the card and its handovers again. */
function reread(): void {
  void list.load()
  void props.card.load({ quiet: true })
}

/** "Show me" from a refusal: the card page takes it from the query. */
function fix(field: StageRequiredField, stageId: string): void {
  void router.replace({ query: { ...route.query, [FOCUS_QUERY_KEY]: field, [ENTER_QUERY_KEY]: stageId } })
}

async function retry(handover: HandoverRead): Promise<void> {
  const result = await list.retryStart(handover)
  if (typeof result === 'string') {
    props.feedback.fail(result)
    return
  }
  if (!result) return
  props.card.detail.value = result.card
  outcome.restarted(result)
}
</script>

<style scoped>
.handover-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.handover-panel__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.handover-panel__text {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.handover-panel__rollup {
  font-size: 12px;
  color: rgb(var(--v-theme-success));
}
.handover-panel__cta {
  align-self: flex-start;
}
</style>
