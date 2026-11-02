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

<!-- A card's page while it loads: a skeleton in the page's shape (reads as
     "forming", not as a hang). -->
<template>
  <div class="card-skeleton" aria-busy="true" aria-label="Loading the card">
    <v-skeleton-loader type="text" width="30%" />
    <v-skeleton-loader type="heading" />
    <v-skeleton-loader type="button@5" />
    <div class="card-skeleton__grid">
      <v-skeleton-loader type="paragraph@4" />
      <v-skeleton-loader type="list-item-two-line@4" />
    </div>
  </div>
</template>

<style scoped>
.card-skeleton {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.card-skeleton__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 20px;
}
@media (max-width: 600px) {
  .card-skeleton__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
