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

<!-- HR sharing one result from its review page, after a confirm. Sharing one
     at a time goes ahead even when the fairness check holds the result back;
     the confirm says so, so HR knows. -->
<template>
  <v-btn color="primary" :loading="busy" @click="open = true">Share with {{ name }}</v-btn>
  <AppConfirmDialog v-model="open" :title="`Share with ${name}?`" :body="body" :action="`Share with ${name}`" :busy="busy" @confirm="confirm" />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'

const props = defineProps<{ name: string; held: boolean; busy: boolean }>()
const emit = defineEmits<{ share: [] }>()
const open = ref(false)

const body = computed(() => {
  const held = props.held ? 'This result is held back in the fairness check. ' : ''
  return `${held}${props.name} gets a Slack message and can read it straight away. Sharing can't be undone.`
})

function confirm(): void {
  open.value = false
  emit('share')
}
</script>
