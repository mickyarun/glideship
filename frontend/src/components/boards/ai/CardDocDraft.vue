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

<!-- An AI draft of a card document, waiting for review: what it changes
     against the current version (or the draft itself, rendered), and for
     editors Accept, Edit then accept, and Reject (which asks first). Nothing
     changes on the card until it's accepted; accepting makes a new version,
     so it can be undone from the version history. Editing the draft before
     accepting asks before it's dropped, like any unsaved edit. -->
<template>
  <section class="doc-draft" :aria-label="`AI draft of the ${DOC_NAMES[kind]}`">
    <CardDocDraftHead
      :kind="kind" :draft="draft" :current="current" :skill-name="skillName" :can-review="canReview"
      :editing="editing" :busy="review.busy.value"
      @accept="accept()" @edit="startEdit" @reject="rejecting = true"
    />
    <AppCallout v-if="note" variant="warning" role="alert">{{ note }}</AppCallout>
    <template v-if="editing">
      <v-textarea
        v-model="text" :label="`${DOC_LABELS[kind]} draft (markdown)`" variant="outlined" rows="12" auto-grow autofocus
        :counter="maxLength ?? undefined" :maxlength="maxLength ?? undefined"
      />
      <div class="doc-draft__actions">
        <v-btn variant="text" size="small" @click="stopEdit">Cancel</v-btn>
        <v-btn variant="flat" color="primary" size="small" :loading="review.busy.value === 'accept'" @click="accept(text)">
          Accept my edit
        </v-btn>
      </div>
    </template>
    <template v-else>
      <AppPillToggle v-model="view" :options="VIEWS" aria-label="Show" class="doc-draft__views" />
      <span class="doc-draft__against">
        {{ current ? `Showing the draft against version ${current.version}` : `The card has no ${DOC_NAMES[kind]} yet` }}
      </span>
      <DiffView v-if="view === 'changes'" :old="current?.body_md ?? ''" :new="draft.body_md" :label="`${DOC_LABELS[kind]} draft changes`" />
      <div v-else class="markdown-body doc-draft__preview" v-html="html" />
    </template>
    <AppConfirmDialog
      v-model="rejecting"
      :title="`Reject this ${DOC_NAMES[kind]} draft?`"
      :body="`The card keeps its ${current ? `current ${DOC_NAMES[kind]} (version ${current.version})` : DOC_NAMES[kind] + ' as it is'}. You can run the agent again later.`"
      action="Reject"
      color="error"
      :busy="review.busy.value === 'reject'"
      @confirm="reject"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import CardDocDraftHead from '@/components/boards/ai/CardDocDraftHead.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import DiffView from '@/components/common/DiffView.vue'
import { useDraftReview } from '@/composables/useDraftReview'
import { DOC_LABELS, DOC_NAMES } from '@/constants/boards'
import type { CardDocKind, DocRead } from '@/types/boards'
import { renderMarkdown } from '@/utils/markdown'

type View = 'changes' | 'preview'
const VIEWS: { label: string; value: View }[] = [
  { label: 'Changes', value: 'changes' },
  { label: 'Preview', value: 'preview' },
]

const props = defineProps<{
  kind: CardDocKind
  draft: DocRead
  current: DocRead | undefined
  skillName: string
  canReview: boolean
  maxLength: number | null
}>()
const emit = defineEmits<{
  result: [error: string | null, success: string]
  dirty: [what: string | null]
}>()

const review = useDraftReview()
const view = ref<View>('changes')
const editing = ref(false)
const text = ref('')
const rejecting = ref(false)
/** Why the last accept didn't go through, shown above the draft. */
const note = ref('')
const html = computed(() => renderMarkdown(props.draft.body_md))
const dirty = computed(() => editing.value && text.value !== props.draft.body_md)

function startEdit(): void {
  text.value = props.draft.body_md
  editing.value = true
}

function stopEdit(): void {
  editing.value = false
  note.value = ''
}

async function accept(body?: string): Promise<void> {
  note.value = ''
  const base = props.current?.version ?? null
  const result = await review.accept(props.draft, base, body)
  if (result.conflict) {
    note.value = result.error ?? ''
    return
  }
  const version = result.error ? '' : ` as version ${(base ?? 0) + 1}`
  emit('result', result.error, `Accepted the ${DOC_NAMES[props.kind]} draft${version}`)
  if (!result.error) editing.value = false
  await review.settle()
}

async function reject(): Promise<void> {
  const error = await review.reject(props.draft)
  rejecting.value = false
  emit('result', error, `Rejected the ${DOC_NAMES[props.kind]} draft`)
  await review.settle()
}

// A newer draft replaces this one: start its review afresh, unless I'm
// part way through editing, which stays (and says what happened).
watch(() => props.draft.id, () => {
  if (dirty.value) {
    note.value = 'A newer draft arrived while you were editing. Your edit is kept, and accepting it saves your text.'
    return
  }
  editing.value = false
  note.value = ''
})
watch(dirty, isDirty => emit('dirty', isDirty ? `the ${DOC_NAMES[props.kind]} draft` : null), { immediate: true })
onBeforeUnmount(() => emit('dirty', null))
</script>

<style scoped>
.doc-draft {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}
.doc-draft__views {
  align-self: flex-start;
}
.doc-draft__against {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.doc-draft__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.doc-draft__preview {
  padding: 16px;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
</style>
