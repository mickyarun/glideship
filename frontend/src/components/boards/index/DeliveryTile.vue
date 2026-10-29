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

<!-- The pinned Delivery tile: the BUD board, for engineering members. -->
<template>
  <article class="delivery-tile">
    <v-icon icon="mdi-source-branch" size="20" class="delivery-tile__icon" aria-hidden="true" />
    <h2 class="delivery-tile__name">
      <router-link :to="item.path" class="delivery-tile__link">{{ item.name }}</router-link>
    </h2>
    <p class="delivery-tile__note">BUDs from requirements to production</p>
  </article>
</template>

<script setup lang="ts">
import type { DeliveryBoardItem } from '@/types/boards'

defineProps<{ item: DeliveryBoardItem }>()
</script>

<style scoped>
.delivery-tile {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 132px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(var(--v-theme-brand), 0.35);
  background: rgba(var(--v-theme-brand), 0.06);
}
.delivery-tile:hover,
.delivery-tile:focus-within {
  border-color: rgba(var(--v-theme-brand), 0.7);
}
.delivery-tile__icon {
  color: rgb(var(--v-theme-brand));
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
.delivery-tile__note {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
