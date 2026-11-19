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

/** The UAT owner choice: shows the saved owner and reports a new pick. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import UatOwnerToggle from '@/components/settings/UatOwnerToggle.vue'

describe('UatOwnerToggle', () => {
  it('marks the saved owner and emits the new one when QA is picked', async () => {
    const wrapper = mount(UatOwnerToggle, { props: { modelValue: 'pm' } })
    const options = wrapper.findAll('[role="radio"]')

    expect(options.map(o => o.text())).toEqual(['Product manager', 'QA'])
    expect(options[0].attributes('aria-checked')).toBe('true')

    await options[1].trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([['qa']])
  })
})
