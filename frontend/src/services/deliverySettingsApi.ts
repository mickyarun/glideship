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

// The Delivery (BUD) board's settings: its AI switch. Anyone who can see
// BUDs reads them; changing them needs org:edit_settings. Mirrors
// backend/app/schemas/delivery_settings.py.

import api from '@/services/api'

const URL = '/v1/settings/delivery'

export interface DeliverySettings {
  /** When off, no BUD stage agent starts; each BUD's own agent choices stay. */
  ai_enabled: boolean
}

export const deliverySettingsApi = {
  get: async () => (await api.get<DeliverySettings>(URL)).data,
  update: async (body: Partial<DeliverySettings>) => (await api.patch<DeliverySettings>(URL, body)).data,
}
