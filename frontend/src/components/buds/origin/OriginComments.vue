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

<!-- The origin card's comments on a BUD, read only and newest first, as
     plain text, with "Show older" while there are more (and why, when
     that failed). Replies go on the card. -->
<template>
  <section class="origin-comments" aria-label="Card comments">
    <span class="origin-comments__label">Card comments · read only</span>
    <p v-if="!comments.length" class="origin-comments__empty">No comments on the card.</p>
    <ol v-else class="origin-comments__list">
      <li v-for="c in comments" :key="c.id" class="origin-comments__item">
        <span class="origin-comments__who">
          <strong>{{ c.author_name ?? c.author_label ?? 'Someone' }}</strong> · {{ formatDate(c.created_at) }}
        </span>
        <span v-if="c.deleted_at" class="origin-comments__empty">Comment deleted.</span>
        <span v-else class="origin-comments__body">{{ c.body }}</span>
      </li>
    </ol>
    <p v-if="error" class="origin-comments__error" role="alert">{{ error }}</p>
    <v-btn v-if="hasMore" variant="text" size="small" :loading="loading" class="align-self-start" @click="emit('more')">
      {{ error ? 'Try again' : 'Show older' }}
    </v-btn>
  </section>
</template>

<script setup lang="ts">
import type { CardCommentRead } from '@/types/boards'
import { formatDate } from '@/utils/date'

defineProps<{ comments: CardCommentRead[]; hasMore: boolean; loading: boolean; error: string }>()
const emit = defineEmits<{ more: [] }>()
</script>

<style scoped>
.origin-comments {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.origin-comments__label {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.origin-comments__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.origin-comments__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 13px;
}
.origin-comments__who {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.origin-comments__body {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.origin-comments__error {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-error));
}
.origin-comments__empty {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
