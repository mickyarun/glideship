// Copyright 2025-2026 Arun Rajkumar
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// The Delivery board's AI switch as its settings show it: loaded once, and
// saved the moment it's flipped (no Save button). Only people who can change
// organization settings flip it; everyone else reads it. While a save is on
// its way the switch shows the new value; a failed one puts it back where
// the server has it and says so.

import { computed, ref } from 'vue'
import { usePermissions } from '@/composables/usePermissions'
import { deliverySettingsApi, type DeliverySettings } from '@/services/deliverySettingsApi'
import { extractApiError } from '@/utils/errors'
import { logFailure } from '@/utils/logFailure'

export function useDeliveryAi() {
  const { hasPermission } = usePermissions()
  const settings = ref<DeliverySettings | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const error = ref('')
  /** The value on its way to the server. */
  const pending = ref<boolean | null>(null)
  const enabled = computed(() => pending.value ?? settings.value?.ai_enabled ?? false)
  const canEdit = computed(() => hasPermission('org:edit_settings'))

  async function load(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      settings.value = await deliverySettingsApi.get()
    } catch (err) {
      logFailure('settings', 'delivery settings fetch', err)
      error.value = extractApiError(err, "Couldn't load the Delivery board's AI setting.")
    } finally {
      loading.value = false
    }
  }

  async function setEnabled(on: boolean): Promise<void> {
    if (!canEdit.value || saving.value) return
    saving.value = true
    pending.value = on
    error.value = ''
    try {
      settings.value = await deliverySettingsApi.update({ ai_enabled: on })
    } catch (err) {
      logFailure('settings', 'delivery settings save', err)
      error.value = extractApiError(err, "Couldn't change the Delivery board's AI. Try again.")
    } finally {
      saving.value = false
      pending.value = null
    }
  }

  return { settings, enabled, loading, saving, error, canEdit, load, setEnabled }
}
