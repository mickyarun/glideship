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

<!-- The card page's overflow menu: copy the card's link, and archive or
     restore it for those who may. -->
<template>
  <v-menu location="bottom end">
    <template #activator="{ props: menuProps }">
      <v-btn v-bind="menuProps" variant="outlined" icon="mdi-dots-horizontal" class="more-menu__btn" aria-label="More card actions" />
    </template>
    <v-list density="compact" min-width="200" aria-label="Card actions">
      <v-list-item prepend-icon="mdi-link-variant" title="Copy link" @click="copy" />
      <template v-if="canArchive">
        <v-divider class="my-1" />
        <v-list-item v-if="archived" prepend-icon="mdi-archive-arrow-up-outline" title="Restore" @click="emit('restore')" />
        <v-list-item v-else base-color="error" prepend-icon="mdi-archive-outline" title="Archive" @click="emit('archive')" />
      </template>
    </v-list>
  </v-menu>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { copyText } from '@/utils/clipboard'

const props = defineProps<{ boardKey: string; number: number; archived: boolean; canArchive: boolean }>()
const emit = defineEmits<{ archive: []; restore: []; copied: [] }>()

const router = useRouter()

async function copy(): Promise<void> {
  const { href } = router.resolve({ name: 'board-card', params: { key: props.boardKey, number: props.number } })
  if (await copyText(new URL(href, window.location.origin).toString())) emit('copied')
}
</script>

<style scoped>
.more-menu__btn {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-input);
  border-color: rgb(var(--v-theme-rule));
}
@media (pointer: coarse) {
  .more-menu__btn {
    width: 44px;
    height: 44px;
  }
}
</style>
