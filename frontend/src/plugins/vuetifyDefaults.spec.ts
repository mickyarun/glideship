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

/** App-wide Vuetify defaults: flat buttons and outlined autocompletes. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { h } from 'vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import { vuetifyDefaults } from '@/plugins/vuetify-theme'

const vuetify = createVuetify({ components, defaults: vuetifyDefaults })
const render = (node: () => ReturnType<typeof h>) =>
  mount({ render: node }, { global: { plugins: [vuetify] } })

describe('vuetifyDefaults', () => {
  it('makes buttons flat unless they ask for another variant', () => {
    expect(render(() => h(components.VBtn, { color: 'primary' }, () => 'Save')).find('.v-btn').classes())
      .toContain('v-btn--variant-flat')
    expect(render(() => h(components.VBtn, { variant: 'outlined' }, () => 'Cancel')).find('.v-btn').classes())
      .toContain('v-btn--variant-outlined')
  })

  it('gives autocompletes the same field look as text fields and selects', () => {
    const { VAutocomplete, VSelect, VTextField } = vuetifyDefaults
    expect(VAutocomplete).toEqual({ variant: 'outlined', density: 'comfortable', color: 'primary' })
    expect(VAutocomplete).toEqual(VSelect)
    expect(VAutocomplete).toEqual(VTextField)
  })
})
