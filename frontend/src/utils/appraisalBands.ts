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

/** The five bands, label first and number second (pure). */

export interface Band {
  value: number
  label: string
}

export const BANDS: Band[] = [
  { value: 1, label: 'Always exceeds' },
  { value: 2, label: 'Exceeds most times' },
  { value: 3, label: 'Meets always' },
  { value: 4, label: 'Meets sometimes' },
  { value: 5, label: 'Does not meet' },
]

export function bandLabel(value: number | null): string {
  return BANDS.find(b => b.value === value)?.label ?? ''
}
