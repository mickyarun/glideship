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

<!-- A Delivery card's ⋯ menu: move the BUD to another stage (the keyboard
     and phone path for anything drag does) and copy its link. Each stage it
     can't go to yet wears a lock and says why; picking it explains and
     offers Open BUD, as a refused drop does. Someone who can't move BUDs,
     or a closed or discarded BUD, gets Copy link only. -->
<template>
  <v-menu location="bottom end">
    <template #activator="{ props: menuProps }">
      <v-btn
        v-bind="menuProps"
        icon="mdi-dots-horizontal"
        variant="text"
        size="x-small"
        density="comfortable"
        class="bud-menu__btn"
        data-no-drag
        :aria-label="`Actions for ${ref}`"
      />
    </template>
    <!-- A menu: the stages are a group of radio items, the current one
         checked; Copy link is a menu item. -->
    <v-list density="compact" min-width="220" role="menu" :aria-label="`Actions for ${ref}`">
      <template v-if="canMove">
        <div role="group" aria-label="Move to stage">
          <v-list-subheader aria-hidden="true">Move to stage</v-list-subheader>
          <v-list-item
            v-for="stage in stages"
            :key="stage"
            role="menuitemradio"
            :aria-checked="stage === bud.status"
            :aria-disabled="stage === bud.status"
            :title="stage === bud.status ? `${BUD_STATUS_LABELS[stage]} (current)` : BUD_STATUS_LABELS[stage]"
            :subtitle="stage === bud.status ? undefined : (blockFor(stage) ?? undefined)"
            :disabled="stage === bud.status"
            @click="emit('move', stage)"
          >
            <template #prepend>
              <v-icon icon="mdi-circle-medium" :color="BUD_STATUS_COLORS[stage]" aria-hidden="true" />
            </template>
            <template v-if="stage !== bud.status && blockFor(stage)" #append>
              <v-icon icon="mdi-lock-outline" size="16" aria-hidden="true" />
            </template>
          </v-list-item>
        </div>
        <v-divider class="my-1" />
      </template>
      <v-list-item role="menuitem" prepend-icon="mdi-link-variant" title="Copy link" @click="copy" />
    </v-list>
  </v-menu>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { BUD_STATUS_COLORS, BUD_STATUS_LABELS, budRef, type BUDListItem, type BUDStatus } from '@/types'
import { copyText } from '@/utils/clipboard'

const props = defineProps<{
  bud: BUDListItem
  /** The stages offered, in lifecycle order. */
  stages: readonly BUDStatus[]
  /** Moving is on (buds:edit or buds:test, and the BUD isn't closed or discarded). */
  canMove: boolean
  /** Why the BUD can't go to a stage yet, or null. */
  blockFor: (stage: BUDStatus) => string | null
}>()

const emit = defineEmits<{ move: [stage: BUDStatus]; copied: [] }>()

const router = useRouter()
const ref = computed(() => budRef(props.bud.bud_number))

async function copy(): Promise<void> {
  const { href } = router.resolve(`/buds/${props.bud.id}`)
  if (await copyText(new URL(href, window.location.origin).toString())) emit('copied')
}
</script>

<style scoped>
/* Above the title link, which stretches over the whole card. */
.bud-menu__btn {
  position: relative;
  z-index: 1;
}
@media (pointer: coarse) {
  .bud-menu__btn {
    min-width: 44px;
    min-height: 44px;
  }
}
</style>
