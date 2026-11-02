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

<!-- A card's Overview tab: its description, checklist, and files and
     links. -->
<template>
  <CardDescription
    data-card-field="description"
    :value="card.description_md"
    :editable="canEdit"
    :max-length="limits?.card_description_max ?? null"
    :save="saveDescription"
    @dirty="what => emit('dirty', what)"
  />
  <CardChecklist
    :list="checklist"
    :editable="canEdit"
    :max-text="limits?.checklist_text_max ?? null"
    :max-items="limits?.checklist_max_items ?? null"
    :compact="compact"
    :remove="removeItem"
    @result="(error, success) => emit('result', error, success)"
  />
  <AppPanel title="Files and links">
    <BugAttachments
      ref="strip"
      :base-url="baseUrl"
      :wire="CARD_ATTACHMENT_WIRE"
      :readonly="!canEdit"
      :can-remove="a => canRemoveAny || a.uploadedBy === meId"
      :max-links="limits?.links_max_per_card ?? null"
      headless
    />
  </AppPanel>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import CardChecklist from '@/components/boards/card/CardChecklist.vue'
import CardDescription from '@/components/boards/card/CardDescription.vue'
import BugAttachments from '@/components/bugs/BugAttachments.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { useCardChecklist } from '@/composables/useCardChecklist'
import { cardUrl } from '@/services/boardsApi'
import { useAuthStore } from '@/stores/auth'
import type { BoardLimits, CardDetail, ChecklistItem } from '@/types/boards'
import { CARD_ATTACHMENT_WIRE } from '@/utils/boardCardWire'

const props = defineProps<{
  card: CardDetail
  boardKey: string
  checklist: ReturnType<typeof useCardChecklist>
  limits: BoardLimits | null
  canEdit: boolean
  /** A board admin may remove anyone's files and links; others only their own. */
  canRemoveAny: boolean
  saveDescription: (text: string) => Promise<boolean>
  removeItem: (item: ChecklistItem) => Promise<boolean>
  /** Phone width. */
  compact: boolean
}>()
const emit = defineEmits<{ result: [error: string | null, success: string]; dirty: [what: string | null] }>()

const auth = useAuthStore()
const meId = computed(() => auth.user?.id ?? null)
const baseUrl = computed(() => cardUrl(props.boardKey, props.card.number))
const strip = ref<InstanceType<typeof BugAttachments> | null>(null)

/** Reload the files and links (someone else changed them). */
defineExpose({ reload: () => strip.value?.reload() })
</script>
