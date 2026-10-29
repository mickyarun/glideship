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

// Single-key page shortcuts. They must never fire while someone is typing,
// or with a modifier held (that's the browser's or the OS's shortcut).

interface KeyLike {
  key: string
  metaKey: boolean
  ctrlKey: boolean
  altKey: boolean
  repeat?: boolean
  defaultPrevented?: boolean
  target: EventTarget | null
}

/** True when the element takes typed text: a field, a select or an editable region. */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!target || typeof (target as Element).closest !== 'function') return false
  const el = target as HTMLElement
  if (el.isContentEditable) return true
  return el.closest('input, textarea, select, [contenteditable=""], [contenteditable="true"]') !== null
}

/** Whether a keydown is the bare ``key`` pressed outside any text field. */
export function isPageShortcut(event: KeyLike, key: string): boolean {
  if (event.defaultPrevented || event.repeat) return false
  if (event.metaKey || event.ctrlKey || event.altKey) return false
  if (event.key.toLowerCase() !== key.toLowerCase()) return false
  return !isTypingTarget(event.target)
}
