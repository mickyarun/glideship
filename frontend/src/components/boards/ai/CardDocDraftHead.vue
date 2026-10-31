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

<!-- The top of an AI draft waiting for review: which agent wrote it and
     when, that accepting makes it the current version (the server numbers
     it, so no number is promised here), a note when the document was saved
     after the draft was written (the comparison uses that newer version, so
     nothing in it is lost), and the review buttons for editors. -->
<template>
  <div class="draft-head">
    <div class="draft-head__text">
      <span class="draft-head__title">
        <v-icon :icon="AI_ICON" size="16" aria-hidden="true" />
        Draft from {{ skillName }} · {{ when }}
      </span>
      <span class="draft-head__meta">
        <span role="status">AI draft of the {{ DOC_NAMES[kind] }}, waiting for review.</span> Would become the current version
      </span>
      <span v-if="stale" class="draft-head__stale">
        Version {{ current?.version }} was saved after this draft was written. The changes below compare the draft with
        version {{ current?.version }}, so nothing in it is lost by accident.
      </span>
      <span v-if="!canReview" class="draft-head__meta">An editor on this board can accept or reject it.</span>
    </div>
    <div v-if="canReview && !editing" class="draft-head__actions">
      <v-btn variant="text" size="small" :disabled="!!busy" :loading="busy === 'reject'" @click="emit('reject')">Reject</v-btn>
      <v-btn variant="outlined" size="small" :disabled="!!busy" @click="emit('edit')">Edit, then accept</v-btn>
      <v-btn variant="flat" color="primary" size="small" :disabled="!!busy" :loading="busy === 'accept'" @click="emit('accept')">
        Accept
      </v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useNow } from '@/composables/useNow'
import { AI_ICON } from '@/constants/boardAgents'
import { DOC_NAMES } from '@/constants/boards'
import type { CardDocKind, DocRead } from '@/types/boards'
import { relativeTime } from '@/utils/date'

const props = defineProps<{
  kind: CardDocKind
  draft: DocRead
  current: DocRead | undefined
  skillName: string
  canReview: boolean
  editing: boolean
  busy: 'accept' | 'reject' | null
}>()
const emit = defineEmits<{ accept: []; edit: []; reject: [] }>()

const now = useNow()
const when = computed(() => relativeTime(props.draft.created_at, now.value))
const stale = computed(() => !!props.current && Date.parse(props.current.created_at) > Date.parse(props.draft.created_at))
</script>

<style scoped>
.draft-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
  padding: 12px 16px;
  border-radius: 8px;
  background: rgba(var(--v-theme-success), 0.08);
  border-left: 3px solid rgb(var(--v-theme-success));
}
.draft-head__text {
  display: flex;
  flex: 1 1 280px;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.draft-head__title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
}
.draft-head__meta,
.draft-head__stale {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.draft-head__stale {
  color: rgb(var(--v-theme-warning));
}
.draft-head__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
