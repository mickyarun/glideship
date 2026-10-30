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

<!-- Links attached to a parent beside its files: each opens in a new tab,
     with Remove for whoever may, and an "Add link" form that stays open
     with its draft until the add succeeds. -->
<template>
  <div class="attachment-links">
    <ul v-if="links.length" class="attachment-links__list">
      <li v-for="link in links" :key="link.id" class="attachment-links__row">
        <v-icon icon="mdi-link-variant" size="16" aria-hidden="true" />
        <a v-if="safeHttpUrl(link.url)" :href="safeHttpUrl(link.url)" target="_blank" rel="noopener noreferrer" class="attachment-links__link">
          {{ link.filename }}<span class="d-sr-only"> (opens in a new tab)</span>
        </a>
        <span v-else class="attachment-links__link">{{ link.filename }}</span>
        <span class="attachment-links__host">{{ hostOf(link.url) }}</span>
        <v-btn
          v-if="canRemove(link)"
          icon="mdi-close"
          variant="text"
          size="x-small"
          class="attachment-links__remove"
          :aria-label="`Remove link ${link.filename}`"
          @click="emit('remove', link.id)"
        />
      </li>
    </ul>

    <form v-if="adding" class="attachment-links__form" @submit.prevent="submit">
      <v-text-field v-model="url" label="Link" type="url" placeholder="https://" variant="outlined" density="compact" hide-details autofocus />
      <v-text-field v-model="title" label="Title (optional)" variant="outlined" density="compact" hide-details />
      <div class="attachment-links__actions">
        <v-btn variant="text" size="small" @click="adding = false">Cancel</v-btn>
        <v-btn type="submit" variant="outlined" size="small" :loading="saving" :disabled="!validUrl">Add link</v-btn>
      </div>
    </form>
    <v-btn
      v-else-if="!readonly && !full"
      variant="text"
      size="small"
      prepend-icon="mdi-link-plus"
      class="attachment-links__open"
      @click="adding = true"
    >
      Add link
    </v-btn>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { StoredAttachment } from '@/utils/attachmentWire'
import { safeHttpUrl } from '@/utils/safeUrl'

const props = defineProps<{
  links: StoredAttachment[]
  readonly: boolean
  canRemove: (link: StoredAttachment) => boolean
  maxLinks: number | null
  add: (url: string, title: string | null) => Promise<boolean>
}>()
const emit = defineEmits<{ remove: [id: string] }>()

const adding = ref(false)
const saving = ref(false)
const url = ref('')
const title = ref('')

const full = computed(() => props.maxLinks !== null && props.links.length >= props.maxLinks)
const validUrl = computed(() => !!safeHttpUrl(url.value.trim()))

function hostOf(link: string | null): string {
  try {
    return link ? new URL(link).host : ''
  } catch {
    return ''
  }
}

async function submit(): Promise<void> {
  if (!validUrl.value || saving.value) return
  saving.value = true
  const ok = await props.add(url.value.trim(), title.value.trim() || null)
  saving.value = false
  if (!ok) return
  url.value = ''
  title.value = ''
  adding.value = false
}
</script>

<style scoped>
.attachment-links__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.attachment-links__row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 0 4px 0 10px;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 8px;
  font-size: 14px;
}
.attachment-links__link {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-accent-text);
  text-decoration: none;
}
.attachment-links__link:hover {
  text-decoration: underline;
}
.attachment-links__host {
  margin-left: auto;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.attachment-links__form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.attachment-links__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
@media (pointer: coarse) {
  .attachment-links__row,
  .attachment-links__open {
    min-height: 44px;
  }
  .attachment-links__remove {
    min-width: 44px;
    min-height: 44px;
  }
}
</style>
