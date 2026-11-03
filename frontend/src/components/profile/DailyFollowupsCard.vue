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

<!--
  The opt-in daily follow-ups DM: one Slack message a day listing the
  signed-in person's overdue and due-soon cards and BUDs. Off by default.
  Every change saves the whole schedule at once (optimistic, reverted on
  error), like the notification switches below it.
-->
<template>
  <v-card color="surface" border class="pa-6">
    <div class="d-flex align-center ga-3 mb-4">
      <v-avatar size="36" color="surface-variant" rounded="lg">
        <v-icon icon="mdi-calendar-check-outline" size="22" />
      </v-avatar>
      <div class="flex-grow-1">
        <div class="text-body-1 font-weight-medium">Daily follow-ups</div>
        <div class="text-caption text-medium-emphasis">
          One Slack message a day with your overdue and due-soon cards and BUDs.
          Nothing is sent on days you have nothing due.
        </div>
      </div>
      <v-switch
        :model-value="form?.enabled ?? false"
        aria-label="Daily follow-ups"
        color="primary"
        hide-details
        density="compact"
        inset
        :loading="saving"
        :disabled="loading || saving || !form"
        @update:model-value="save({ enabled: $event ?? false })"
      />
    </div>

    <div v-if="loading" class="d-flex justify-center py-4">
      <v-progress-circular indeterminate color="primary" size="24" />
    </div>

    <template v-else-if="form?.enabled">
      <div class="d-flex flex-wrap align-center ga-4 mb-4">
        <v-text-field
          :model-value="hhmm"
          label="Send at"
          type="time"
          density="compact"
          variant="outlined"
          hide-details
          style="max-width: 160px;"
          :disabled="saving"
          @change="onTime"
        />
        <AppPillToggle
          :model-value="form.weekdays_only ? 'weekdays' : 'every'"
          :options="dayOptions"
          aria-label="Days to send"
          @update:model-value="save({ weekdays_only: $event === 'weekdays' })"
        />
      </div>
      <AppCallout variant="info" icon="mdi-earth">
        Sent at your local time in <strong>{{ form.timezone }}</strong>. You're skipped on
        days you're on leave or on a holiday.
        <template v-if="form.timezone !== deviceZone" #actions>
          <v-btn variant="text" size="small" :disabled="saving" @click="save({ timezone: deviceZone })">
            Use {{ deviceZone }}
          </v-btn>
        </template>
      </AppCallout>
    </template>

    <AppCallout v-if="error" variant="warning" icon="mdi-alert-outline" class="mt-4">
      {{ error }}
    </AppCallout>
  </v-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import api from '@/services/api'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import type { FollowupSettings } from '@/types'

type Saved = FollowupSettings & { timezone: string }

const URL = '/v1/me/followups'
const DAYS = [
  { label: 'Weekdays', value: 'weekdays' },
  { label: 'Every day', value: 'every' },
]
// The browser's IANA zone, offered when nothing is saved or it differs.
const deviceZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'

const form = ref<Saved | null>(null)
const loading = ref(true)
const saving = ref(false)
const error = ref('')

// Locked while a save is in flight, like the other controls, so saves can't overlap.
const dayOptions = computed(() => DAYS.map(option => ({ ...option, disabled: saving.value })))

// The API speaks "HH:MM:SS"; the time input wants "HH:MM".
const hhmm = computed(() => form.value?.send_time.slice(0, 5) ?? '')

async function load(): Promise<void> {
  try {
    const { data } = await api.get<FollowupSettings>(URL)
    form.value = { ...data, timezone: data.timezone ?? deviceZone }
  } catch {
    error.value = 'Could not load your follow-ups settings. Try refreshing.'
  } finally {
    loading.value = false
  }
}

async function save(change: Partial<Saved>): Promise<void> {
  if (!form.value || saving.value) return
  const previous = form.value
  form.value = { ...previous, ...change } // optimistic
  saving.value = true
  error.value = ''
  try {
    const { data } = await api.put<FollowupSettings>(URL, form.value)
    form.value = { ...data, timezone: data.timezone ?? form.value.timezone }
  } catch {
    form.value = previous // revert
    error.value = 'Could not save that change. Please try again.'
  } finally {
    saving.value = false
  }
}

function onTime(event: Event): void {
  const value = (event.target as HTMLInputElement).value
  if (value && value !== hhmm.value) void save({ send_time: value })
}

onMounted(load)
</script>
