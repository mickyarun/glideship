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

<!-- A card's ⋯ menu: move it to another stage (the keyboard path for
     anything drag does), copy its link, archive it. Items the board's
     capabilities don't allow are left out. -->
<template>
  <v-menu location="bottom end">
    <template #activator="{ props: menuProps }">
      <v-btn
        v-bind="menuProps"
        icon="mdi-dots-horizontal"
        variant="text"
        size="x-small"
        density="comfortable"
        class="card-menu__btn"
        :aria-label="`Actions for ${card.key}`"
      />
    </template>
    <v-list density="compact" min-width="220">
      <template v-if="canMove && targets.length">
        <v-list-subheader>Move to stage</v-list-subheader>
        <v-list-item
          v-for="stage in targets"
          :key="stage.id"
          :title="stage.name"
          prepend-icon="mdi-arrow-right"
          @click="emit('move', stage.id)"
        />
        <v-divider class="my-1" />
      </template>
      <v-list-item prepend-icon="mdi-link-variant" :title="copied ? 'Link copied' : 'Copy link'" @click.stop="copy" />
      <v-list-item
        v-if="canArchive"
        prepend-icon="mdi-archive-outline"
        title="Archive"
        @click="emit('archive')"
      />
    </v-list>
  </v-menu>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { CardSummary, StageRead } from '@/types/boards'
import { copyText } from '@/utils/clipboard'

const props = defineProps<{
  card: CardSummary
  stages: StageRead[]
  boardKey: string
  canMove: boolean
  canArchive: boolean
}>()

const emit = defineEmits<{ move: [stageId: string]; archive: [] }>()

const router = useRouter()
const copied = ref(false)

const targets = computed(() => props.stages.filter(s => s.id !== props.card.stage_id))

async function copy(): Promise<void> {
  const { href } = router.resolve({
    name: 'board-card',
    params: { key: props.boardKey, number: props.card.number },
  })
  copied.value = await copyText(new URL(href, window.location.origin).toString())
}
</script>

<style scoped>
@media (pointer: coarse) {
  .card-menu__btn {
    min-width: 44px;
    min-height: 44px;
  }
}
</style>
