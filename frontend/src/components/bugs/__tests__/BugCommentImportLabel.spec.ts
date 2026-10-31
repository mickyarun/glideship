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

/** A card comment that came in with an import says so ("via Trello import"); others don't. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import BugCommentItem from '@/components/bugs/BugCommentItem.vue'
import type { CardCommentRead } from '@/types/boards'
import { CARD_COMMENT_WIRE } from '@/utils/boardCardWire'

const wire = (over: Partial<CardCommentRead>): CardCommentRead => ({
  id: 'c1', author_id: null, author_label: 'Priya (Trello)', author_name: null, author_avatar_url: null,
  body: 'Shipped the fix', edited_at: null, deleted_at: null, created_at: '2026-10-01T00:00:00Z', ...over,
})

function render(over: Partial<CardCommentRead>) {
  const comment = CARD_COMMENT_WIRE.one(wire(over))
  return mount(BugCommentItem, {
    props: { comment, editing: false, canModify: false },
    global: { plugins: [createVuetify({ components, directives })] },
  })
}

describe('imported comments', () => {
  it('show where they came from beside the author', () => {
    const wrapper = render({ import_source: 'trello' })
    expect(wrapper.text()).toContain('Priya (Trello)')
    expect(wrapper.text()).toContain('via Trello import')
  })

  it('leave comments written here alone', () => {
    expect(render({ import_source: null, author_id: 'u1', author_name: 'Sam' }).text()).not.toContain('import')
    expect(render({}).text()).not.toContain('via')
  })
})
