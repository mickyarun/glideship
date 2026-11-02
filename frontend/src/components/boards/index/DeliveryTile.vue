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

<!-- The pinned Delivery tile, full width: the board of type Delivery (BUDs), for engineering
     members, with its stages. -->
<template>
  <article class="delivery-tile">
    <div class="delivery-tile__top">
      <h2 class="delivery-tile__name">
        <router-link :to="item.path" class="delivery-tile__link">{{ item.name }}</router-link>
      </h2>
      <span class="delivery-tile__chip">{{ DELIVERY_BOARD.key }}</span>
      <span class="delivery-tile__note">{{ DELIVERY_BOARD.type }} · built in · engineering access</span>
    </div>
    <p class="delivery-tile__note">Where cards land when they're handed over. Holds every BUD.</p>
    <ul class="delivery-tile__stages" aria-label="Stages">
      <li
        v-for="stage in STAGES"
        :key="stage"
        class="delivery-tile__stage"
        :style="{ '--stage': `var(--v-theme-${BUD_STATUS_COLORS[stage]})` }"
      >
        {{ BUD_STATUS_LABELS[stage] }}
      </li>
    </ul>
  </article>
</template>

<script setup lang="ts">
import { BUD_STATUS_COLORS, BUD_STATUS_LABELS, type BUDStatus } from '@/types'
import { DELIVERY_BOARD } from '@/constants/boards'
import type { DeliveryBoardItem } from '@/types/boards'

defineProps<{ item: DeliveryBoardItem }>()

/** The BUD stages from first to live; closed and discarded aren't stages of work. */
const STAGES: BUDStatus[] = ['bud', 'design', 'tech_arch', 'development', 'code_review', 'testing', 'uat', 'prod']
</script>

<style scoped>
.delivery-tile {
  grid-column: 1 / -1;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(var(--v-theme-brand), 0.35);
  background: rgba(var(--v-theme-brand), 0.06);
}
.delivery-tile:hover,
.delivery-tile:focus-within {
  border-color: rgba(var(--v-theme-brand), 0.7);
}
.delivery-tile__top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.delivery-tile__name {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.delivery-tile__link {
  color: inherit;
  text-decoration: none;
}
.delivery-tile__link::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
}
.delivery-tile__link:focus-visible {
  outline: none;
}
.delivery-tile__link:focus-visible::after {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
.delivery-tile__chip {
  padding: 1px 7px;
  border-radius: 6px;
  font: 600 11px var(--font-mono);
  color: rgb(var(--v-theme-brand));
  background: rgba(var(--v-theme-brand), 0.14);
}
.delivery-tile__note {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.delivery-tile__stages {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}
/* The stage's colour is its dot and tint; the text stays the regular
   colour, as the stage colours are too light to read at this size. */
.delivery-tile__stage {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface));
  background: rgba(var(--stage), 0.12);
}
.delivery-tile__stage::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: rgb(var(--stage));
}
</style>
