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
import { computed, ref, type ComputedRef } from 'vue'
import { usePermissions } from '@/composables/usePermissions'
import api from '@/services/api'
import type { UatOwner } from '@/stores/settings'

/**
 * The org's UAT owner, read from GET /settings/bud-stages, which anyone who
 * can see BUDs may call (the full settings read needs integrations:view,
 * which QA lacks). When QA owns UAT, QA may also move a BUD from UAT to
 * Prod or back to Development. Only a QA-only user (buds:test without
 * buds:edit) is ever limited by it, so only they read it. Loaded once per
 * page load and shared; until it answers, or if it fails, the default owner
 * (the PM) applies, so QA sees no extra moves rather than ones the server
 * would refuse.
 */
const uatOwner = ref<UatOwner>('pm')
let loading: Promise<void> | null = null

function load(): Promise<void> {
  if (loading) return loading
  const request: Promise<void> = api
    .get<{ uatOwner?: UatOwner }>('/v1/settings/bud-stages')
    .then(({ data }) => {
      // A save or sign-out since this read started wins over its answer.
      if (loading === request && data.uatOwner) uatOwner.value = data.uatOwner
    })
    .catch(() => {
      if (loading === request) loading = null // try again on the next screen that asks
    })
  loading = request
  return request
}

export function useBudStageSettings(): { qaOwnsUat: ComputedRef<boolean> } {
  const { hasPermission } = usePermissions()
  if (hasPermission('buds:test') && !hasPermission('buds:edit')) void load()
  return { qaOwnsUat: computed(() => uatOwner.value === 'qa') }
}

/**
 * Set the owner an admin just saved, so the BUD screens use it without
 * another read. With no owner (sign-out), forget it and read again next time.
 */
export function resetBudStageSettings(owner?: UatOwner): void {
  uatOwner.value = owner ?? 'pm'
  loading = owner ? Promise.resolve() : null
}
