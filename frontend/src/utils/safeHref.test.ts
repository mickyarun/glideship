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

/** Only an https address becomes a link; anything else renders as text. */
import { describe, expect, it } from 'vitest'
import { safeHref } from '@/utils/safeHref'

describe('safeHref', () => {
  it('keeps an https address', () => {
    expect(safeHref('https://github.com/northwind/web')).toBe('https://github.com/northwind/web')
  })

  it('drops script, data, plain http, relative and broken addresses', () => {
    for (const url of ['javascript:alert(1)', 'JaVaScRiPt:alert(1)', 'data:text/html,x', 'http://x.dev', '/repos/1', 'not a url', '', null, undefined]) {
      expect(safeHref(url)).toBeNull()
    }
  })
})
