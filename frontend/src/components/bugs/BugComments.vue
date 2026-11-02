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

<!-- A comment thread (a bug's, a board card's): the comments, oldest
     first, with "Show more" while the thread has more pages, each one's
     edit and delete for whoever may, and the composer. The parent hands
     in the thread (stores/commentThread.ts), so the same list serves any
     parent's comments. ``closed`` (an archived card) shows why nobody can
     reply, with no composer and no edit or delete. ``headless`` drops
     the heading inside a panel that already has one. -->
<template>
  <div>
    <div v-if="!headless" class="text-subtitle-2 font-weight-medium mb-2 d-flex align-center ga-2">
      <v-icon icon="mdi-comment-text-outline" size="18" />
      <span>Comments</span>
      <v-chip v-if="thread.activeCount > 0" size="x-small" variant="tonal" color="primary">
        {{ thread.activeCount }}
      </v-chip>
    </div>

    <div v-if="thread.loading" class="d-flex justify-center py-3">
      <v-progress-circular indeterminate size="20" />
    </div>

    <div v-else-if="thread.comments.length === 0" class="text-caption text-medium-emphasis pa-3 text-center">
      {{ closed ?? 'No comments yet. Be the first.' }}
    </div>

    <div v-else class="d-flex flex-column ga-2 mb-3">
      <BugCommentItem
        v-for="comment in thread.comments"
        :key="comment.id"
        :comment="comment"
        :editing="editingId === comment.id"
        :can-modify="canModify(comment)"
        @edit="editingId = comment.id"
        @cancel="editingId = null"
        @save="saveEdit(comment.id, $event)"
        @delete="thread.remove(comment.id)"
      />
      <v-btn
        v-if="thread.next"
        variant="text"
        size="small"
        class="align-self-start"
        :loading="thread.loadingMore"
        @click="thread.loadMore()"
      >
        Show more comments
      </v-btn>
    </div>

    <p v-if="closed && thread.comments.length" class="text-caption text-medium-emphasis mb-0">{{ closed }}</p>
    <v-textarea
      v-if="canReply"
      v-model="newBody"
      label="Add a comment"
      variant="outlined"
      density="compact"
      rows="2"
      hide-details
      class="mb-2"
      :maxlength="maxLength"
      :disabled="posting"
    />
    <div v-if="canReply" class="d-flex justify-end">
      <v-btn
        color="primary"
        variant="flat"
        size="small"
        :disabled="!newBody.trim() || posting"
        :loading="posting"
        @click="onPost"
      >
        Post
      </v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import type { CommentThread, ThreadComment } from '@/stores/commentThread'
import BugCommentItem from './BugCommentItem.vue'

const props = defineProps<{
  thread: CommentThread
  canComment: boolean
  /** May edit and delete anyone's comments, not only their own. */
  canModerate: boolean
  maxLength?: number
  /** Why the thread is closed (no replies, edits or deletes), when it is. */
  closed?: string | null
  headless?: boolean
}>()

const canReply = computed(() => props.canComment && !props.closed)

const authStore = useAuthStore()

const newBody = ref('')
const posting = ref(false)
const editingId = ref<string | null>(null)

watch(
  () => props.thread,
  thread => {
    void thread.fetch()
    editingId.value = null
    newBody.value = ''
  },
  { immediate: true },
)

function canModify(comment: ThreadComment): boolean {
  if (comment.deletedAt || props.closed) return false
  if (!authStore.user) return false
  if (comment.authorId === authStore.user.id) return true
  return props.canModerate
}

async function saveEdit(commentId: string, body: string): Promise<void> {
  if (!body) return
  const updated = await props.thread.edit(commentId, body)
  if (updated) editingId.value = null
}

async function onPost(): Promise<void> {
  if (!newBody.value.trim()) return
  posting.value = true
  const added = await props.thread.add(newBody.value.trim())
  posting.value = false
  if (added) newBody.value = ''
}
</script>
