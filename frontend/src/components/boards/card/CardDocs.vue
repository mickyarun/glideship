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

<!-- A card's Documents tab: pick the PRD, design brief or notes; read or
     edit it; and its versions beside it, with the card's AI below them
     (the ``aside`` slot). Picking an older version shows what changed
     since, with Restore. An AI draft waiting for review shows in the
     document's place until it's accepted or rejected. Switching document
     or version over an unsaved edit asks first. -->
<template>
  <div class="card-docs">
    <AppPillToggle
      :model-value="kind"
      :options="kindOptions"
      class="card-docs__kinds"
      aria-label="Document"
      @update:model-value="pickKind"
    />
    <AppCallout v-if="docs.error" variant="error" role="alert" :title="`The ${DOC_NAMES[kind]} didn't load`">
      {{ docs.error }}
      <template #actions>
        <v-btn variant="outlined" size="small" @click="docs.refresh(kind)">Try again</v-btn>
      </template>
    </AppCallout>
    <div class="card-docs__grid">
      <div class="card-docs__main" :data-card-field="kind">
        <v-skeleton-loader v-if="docs.loading" type="paragraph@3" />
        <CardDocCompare
          v-else-if="comparing"
          :kind="kind"
          :version="comparing"
          :current-text="doc?.body_md ?? ''"
          :current-version="doc?.version ?? null"
          :can-edit="canEdit"
          @close="closeCompare"
          @result="(error, success) => emit('result', error, success)"
        />
        <CardDocDraft
          v-else-if="aiDraft && !editorDirty"
          :kind="kind" :draft="aiDraft" :current="doc" :skill-name="agents.skillName(aiDraft.agent_run_id)"
          :can-review="canReview" :max-length="maxLength"
          @result="(error, success) => emit('result', error, success)"
          @dirty="what => { draft = what; emit('dirty', what) }"
        />
        <template v-else>
          <!-- A draft that lands mid-edit waits: the edit is never swapped away. -->
          <AppCallout v-if="aiDraft" variant="info" role="status" class="mb-3">
            An AI draft of the {{ DOC_NAMES[kind] }} arrived. Save or cancel your edit to review it.
          </AppCallout>
          <CardDocEditor
            :key="kind"
            :kind="kind"
            :doc="doc"
            :card-key="cardKey"
            :can-edit="canEdit"
            :max-length="maxLength"
            :confirm-discard="confirmDiscard"
            @result="(error, success) => emit('result', error, success)"
            @dirty="what => { draft = what; editorDirty = !!what; emit('dirty', what) }"
          />
        </template>
      </div>
      <aside class="card-docs__aside" :aria-label="`${DOC_LABELS[kind]} versions`">
        <CardDocVersions :kind="kind" :selected-id="compareId" :name-for="nameFor" @select="select" />
        <slot name="aside" />
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import CardDocDraft from '@/components/boards/ai/CardDocDraft.vue'
import CardDocCompare from '@/components/boards/card/CardDocCompare.vue'
import CardDocEditor from '@/components/boards/card/CardDocEditor.vue'
import CardDocVersions from '@/components/boards/card/CardDocVersions.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import { DOC_KINDS, DOC_LABELS, DOC_NAMES } from '@/constants/boards'
import { useBoardCardAgentsStore } from '@/stores/boardCardAgents'
import { useBoardCardDocsStore } from '@/stores/boardCardDocs'
import type { CardDocKind } from '@/types/boards'

const props = defineProps<{
  cardKey: string
  canEdit: boolean
  /** Editors accept or reject AI drafts. */
  canReview: boolean
  maxLength: number | null
  nameFor: (id: string) => string
  /** Asks before an open draft is thrown away; resolves true to go ahead. */
  confirmDiscard: () => Promise<boolean>
}>()
const emit = defineEmits<{ result: [error: string | null, success: string]; dirty: [what: string | null] }>()

const docs = useBoardCardDocsStore()
const agents = useBoardCardAgentsStore()
/** The document shown; the page sets it too (to the PRD, for a stage that needs one). */
const kind = defineModel<CardDocKind>('kind', { default: DOC_KINDS[0] })
const compareId = ref<string | null>(null)
/** What the editor has unsaved, if anything. */
const draft = ref<string | null>(null)
/** The editor has unsaved text, so an AI draft arriving waits behind it. */
const editorDirty = ref(false)
const kindOptions = computed(() =>
  DOC_KINDS.map(k => ({ label: docs.drafts[k] ? `${DOC_LABELS[k]} · AI draft` : DOC_LABELS[k], value: k })),
)

const doc = computed(() => docs.current[kind.value])
const aiDraft = computed(() => docs.drafts[kind.value])
const history = computed(() => docs.history[kind.value])
const comparing = computed(() => history.value?.items.find(v => v.id === compareId.value) ?? null)

/** Go ahead only when there's no draft, or I agree to drop it. */
async function leaveDraft(): Promise<boolean> {
  return !draft.value || props.confirmDiscard()
}

async function pickKind(next: CardDocKind): Promise<void> {
  if (next !== kind.value && (await leaveDraft())) kind.value = next
}

async function select(id: string): Promise<void> {
  const picked = history.value?.items.find(v => v.id === id)
  // The current version has nothing to compare with; show the document.
  const next = !picked || picked.version === doc.value?.version ? null : id
  if (next !== compareId.value && (await leaveDraft())) compareId.value = next
}

/** Back to the document, with focus on the version that was open. */
async function closeCompare(): Promise<void> {
  const id = compareId.value
  compareId.value = null
  await nextTick()
  document.querySelector<HTMLElement>(`[data-version-id="${id}"]`)?.focus()
}

// A new kind, or a new card opened under the tab: load that history.
watch([kind, () => docs.card], ([k]) => {
  compareId.value = null
  if (!docs.history[k]?.loaded) void docs.loadVersions(k)
}, { immediate: true })
</script>

<style scoped>
.card-docs {
  display: flex;
  flex-direction: column;
  gap: 16px;
  container: card-docs / inline-size;
}
.card-docs__kinds {
  align-self: flex-start;
}
.card-docs__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 20px;
  align-items: start;
}
.card-docs__main {
  min-width: 0;
}
.card-docs__aside {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
@container card-docs (max-width: 860px) {
  .card-docs__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
