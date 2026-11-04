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

<!-- The four headings with the person's own lines and links under each.
     An empty heading says so and offers "Add a line" and "Add a link" right
     there, so nobody hunts for a box further down the page. Lines are kept
     in the parent's draft and saved with the page; links save at once. -->
<template>
  <section class="headings" aria-labelledby="checkin-headings">
    <h2 id="checkin-headings" class="headings__title">{{ editable ? 'In your words' : 'In their words' }}</h2>
    <div v-for="heading in HEADINGS" :key="heading.value" class="heading">
      <h3 class="heading__name">{{ heading.label }}</h3>
      <p v-if="meanings[heading.value]" class="heading__meaning">{{ meanings[heading.value] }}</p>
      <ul v-if="lines[heading.value]?.length || linksUnder(heading.value).length" class="heading__items">
        <li v-for="(line, i) in lines[heading.value] ?? []" :key="`l${i}`" class="heading__item">
          <v-text-field
            v-if="editable"
            :model-value="line"
            :aria-label="`${heading.label}, line ${i + 1}`"
            density="compact"
            hide-details
            maxlength="300"
            @update:model-value="(v: string) => setLine(heading.value, i, v)"
          />
          <span v-else>{{ line }}</span>
          <v-btn v-if="editable" icon="mdi-close" variant="text" size="small" :aria-label="`Remove line ${i + 1}`" @click="removeLine(heading.value, i)" />
        </li>
        <li v-for="link in linksUnder(heading.value)" :key="link.id" class="heading__item">
          <a v-if="safeHref(link.url)" :href="safeHref(link.url) ?? undefined" target="_blank" rel="noopener noreferrer">{{ link.title || link.url }}</a>
          <span v-else>{{ link.title || link.url }}</span>
          <span class="heading__added">added by {{ editable ? 'you' : 'them' }}</span>
          <v-btn v-if="editable" icon="mdi-close" variant="text" size="small" :aria-label="`Remove link ${link.title || link.url}`" @click="emit('remove-link', link.id)" />
        </li>
      </ul>
      <p v-else-if="editable" class="heading__empty">Glideship has nothing here this month. Anything worth recording?</p>
      <p v-else class="heading__empty">Nothing under this heading.</p>
      <template v-if="editable">
        <div v-if="isAdding(heading.value)" class="heading__link-form">
          <v-text-field v-model="linkUrl" label="Link" placeholder="https://" density="compact" hide-details />
          <v-text-field v-model="linkTitle" label="Short title" density="compact" hide-details maxlength="200" />
          <v-btn size="small" color="primary" :disabled="!linkUrl.trim()" @click="submitLink(heading.value)">Add</v-btn>
          <v-btn size="small" variant="text" @click="addingLink = null">Cancel</v-btn>
        </div>
        <div v-else class="heading__actions">
          <v-btn size="small" variant="outlined" prepend-icon="mdi-plus" @click="addLine(heading.value)">Add a line</v-btn>
          <v-btn size="small" variant="outlined" prepend-icon="mdi-link-variant" :disabled="linksFull" @click="startLink(heading.value)">Add a link</v-btn>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CheckInLink, EvidenceHeading } from '@/types/appraisal'
import { HEADINGS, safeHref } from '@/utils/appraisalCheckIn'

const MAX_LINKS = 5

const props = defineProps<{
  lines: Partial<Record<EvidenceHeading, string[]>>
  links: CheckInLink[]
  meanings: Partial<Record<EvidenceHeading, string>>
  editable: boolean
}>()
const emit = defineEmits<{
  'update:lines': [lines: Partial<Record<EvidenceHeading, string[]>>]
  'add-link': [heading: EvidenceHeading, url: string, title: string]
  'remove-link': [linkId: string]
}>()

const addingLink = ref<EvidenceHeading | null>(null)
const linkUrl = ref('')
const linkTitle = ref('')
const linksFull = computed(() => props.links.length >= MAX_LINKS)

function startLink(heading: EvidenceHeading): void {
  addingLink.value = heading
}

function isAdding(heading: EvidenceHeading): boolean {
  return addingLink.value === heading
}

function linksUnder(heading: EvidenceHeading): CheckInLink[] {
  return props.links.filter(l => l.heading === heading)
}

function update(heading: EvidenceHeading, next: string[]): void {
  emit('update:lines', { ...props.lines, [heading]: next })
}

function addLine(heading: EvidenceHeading): void {
  update(heading, [...(props.lines[heading] ?? []), ''])
}

function setLine(heading: EvidenceHeading, index: number, text: string): void {
  update(heading, (props.lines[heading] ?? []).map((line, i) => (i === index ? text : line)))
}

function removeLine(heading: EvidenceHeading, index: number): void {
  update(heading, (props.lines[heading] ?? []).filter((_, i) => i !== index))
}

function submitLink(heading: EvidenceHeading): void {
  emit('add-link', heading, linkUrl.value.trim(), linkTitle.value.trim())
  linkUrl.value = ''
  linkTitle.value = ''
  addingLink.value = null
}
</script>

<style scoped>
.headings {
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.headings__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.heading {
  padding-top: 12px;
  margin-top: 12px;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.heading__name {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}
.heading__meaning,
.heading__empty,
.heading__added {
  margin: 2px 0 0;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.heading__items {
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.heading__item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}
.heading__item > :first-child {
  flex: 1 1 auto;
  min-width: 0;
}
.heading__actions,
.heading__link-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 8px;
}
.heading__link-form .v-text-field {
  flex: 1 1 200px;
}
</style>
