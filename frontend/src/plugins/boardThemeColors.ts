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

// Board stage-category and card-label hues, spread into both themes in
// vuetify-theme.ts. They mirror tokens.css (--color-category-* and
// --color-label-*). Each reads at 4.5:1 or better as tag text on a wash of
// itself over the card surface; the BUD stage-* hues stay separate.

export const boardColorsDark: Record<string, string> = {
  'category-todo': '#94A3B8',
  'category-in-progress': '#60A5FA',
  'category-done': '#4ADE80',
  'category-canceled': '#FCA5A5',
  'label-green': '#4ADE80',
  'label-yellow': '#FACC15',
  'label-orange': '#FB923C',
  'label-red': '#F87171',
  'label-purple': '#C084FC',
  'label-blue': '#60A5FA',
  'label-sky': '#38BDF8',
  'label-lime': '#A3E635',
  'label-pink': '#F472B6',
  'label-black': '#CBD5E1',
}

export const boardColorsLight: Record<string, string> = {
  'category-todo': '#475569',
  'category-in-progress': '#1D4ED8',
  'category-done': '#166534',
  'category-canceled': '#B91C1C',
  'label-green': '#166534',
  'label-yellow': '#854D0E',
  'label-orange': '#9A3412',
  'label-red': '#B91C1C',
  'label-purple': '#7E22CE',
  'label-blue': '#1D4ED8',
  'label-sky': '#0369A1',
  'label-lime': '#3F6212',
  'label-pink': '#BE185D',
  'label-black': '#1F2937',
}
