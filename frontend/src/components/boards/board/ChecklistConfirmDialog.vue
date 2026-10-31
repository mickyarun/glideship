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

<!-- Asks before a card with open checklist items completes in a Done stage
     ("2 of 3 checklist items are still open. Move SEO-4 to Done anyway?").
     The question and its answer live in useChecklistConfirm. -->
<template>
  <AppConfirmDialog
    :model-value="confirm.asking.value"
    title="Checklist still open"
    :body="confirm.question.value"
    action="Move anyway"
    @update:model-value="open => !open && confirm.answer(false)"
    @confirm="confirm.answer(true)"
  />
</template>

<script setup lang="ts">
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import type { ChecklistConfirm } from '@/composables/useStageEntry'

defineProps<{ confirm: ChecklistConfirm }>()
</script>
