<!--
 * Copyright 2025-2026 Arun Rajkumar
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 -->

<!-- Pill-shaped segmented control.

     Renders a primary-coloured pill track with N options; the
     active option flips to a surface-coloured pill with
     primary-coloured text. Built on a plain ``<button>`` per option
     because Vuetify's ``v-btn-toggle`` paints the active state via
     internal overlays that fight our active-pill-on-track design.

     Usage:
       <AppPillToggle
         v-model="mode"
         :options="[{ label: 'Create', value: 'create' }, ...]"
       />

     v-model is the value of the selected option. ``mandatory`` (the
     default) prevents clicks on the active option from deselecting
     it — useful when the parent assumes a non-null mode at all
     times. -->
<template>
  <div ref="root" class="app-pill-toggle" :class="`app-pill-toggle--${size}`" role="radiogroup" @keydown="onKey">
    <button
      v-for="opt in options"
      :key="String(opt.value)"
      type="button"
      role="radio"
      class="app-pill-toggle__option"
      :class="{ 'app-pill-toggle__option--active': opt.value === modelValue }"
      :aria-checked="opt.value === modelValue"
      :tabindex="opt.value === focusValue ? 0 : -1"
      @click="select(opt.value)"
    >
      {{ opt.label }}
    </button>
  </div>
</template>

<script setup lang="ts" generic="T extends string | number">
import { computed, nextTick, ref } from 'vue'

interface PillOption<V extends string | number> {
  label: string
  value: V
}

interface Props {
  modelValue: T
  options: PillOption<T>[]
  // When true (default), clicking the already-active option does
  // nothing — the parent always sees a non-null model value.
  mandatory?: boolean
  // ``md`` (default) matches the v-tabs density="compact" height
  // (34px). ``sm`` is for tight chrome (e.g. card headers). ``touch``
  // is for a row of many options that scrolls sideways (phone tabs): the
  // track grows with its options instead of squeezing them, and each is
  // 44px tall on touch screens.
  size?: 'sm' | 'md' | 'touch'
}

const props = withDefaults(defineProps<Props>(), {
  mandatory: true,
  size: 'md',
})

const emit = defineEmits<(e: 'update:modelValue', value: T) => void>()

const root = ref<HTMLElement | null>(null)
// One tab stop for the group (the checked option, else the first); arrow
// keys move between options and pick them, as radio groups do.
const focusValue = computed(() =>
  props.options.some(o => o.value === props.modelValue) ? props.modelValue : props.options[0]?.value,
)

const STEPS: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }

function onKey(event: KeyboardEvent): void {
  const count = props.options.length
  const at = props.options.findIndex(o => o.value === focusValue.value)
  let next: number
  if (event.key in STEPS) next = (at + STEPS[event.key] + count) % count
  else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = count - 1
  else return
  event.preventDefault()
  select(props.options[next].value)
  void nextTick(() => root.value?.querySelectorAll<HTMLElement>('[role="radio"]')[next]?.focus())
}

function select(value: T): void {
  if (props.mandatory && value === props.modelValue) return
  emit('update:modelValue', value)
}
</script>

<style scoped>
.app-pill-toggle {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 3px;
  background: rgb(var(--v-theme-primary));
  border-radius: 999px;
  flex-shrink: 0;
}
.app-pill-toggle--sm {
  height: 28px;
}
.app-pill-toggle--sm .app-pill-toggle__option {
  height: 22px;
  font-size: 11px;
  padding: 0 12px;
  min-width: 64px;
}
.app-pill-toggle--md {
  height: 34px;
}
.app-pill-toggle--md .app-pill-toggle__option {
  height: 28px;
  font-size: 12px;
  padding: 0 18px;
  min-width: 84px;
}
.app-pill-toggle--touch {
  width: max-content;
  min-height: 36px;
}
.app-pill-toggle--touch .app-pill-toggle__option {
  flex-shrink: 0;
  min-height: 30px;
  padding: 0 16px;
  font-size: 13px;
  white-space: nowrap;
}
.app-pill-toggle__option {
  /* Reset the user-agent <button> styles, then drive everything from
     here. Labels use the theme's on-primary ink (white on the light
     theme's blue, near-black on the dark theme's lighter blue) so both
     clear 4.5:1 on the track. */
  appearance: none;
  -webkit-appearance: none;
  border: none;
  background: transparent;
  color: rgb(var(--v-theme-on-primary));
  font-family: inherit;
  font-weight: 600;
  letter-spacing: 0;
  text-transform: none;
  border-radius: 999px;
  cursor: pointer;
  transition:
    background-color var(--dur-short, 150ms) ease,
    color var(--dur-short, 150ms) ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
/* Hover shades the track towards the surface ink, which keeps the label
   at about 6.0:1 on the light theme and 8.1:1 on the dark one. */
.app-pill-toggle__option:hover:not(.app-pill-toggle__option--active) {
  background: rgba(var(--v-theme-on-surface), 0.12);
}
/* The active pill is a surface-coloured cut-out showing the primary ink:
   5.2:1 on the light theme, 7.0:1 on the dark theme. */
.app-pill-toggle__option--active {
  background: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-primary));
  cursor: default;
}
@media (pointer: coarse) {
  .app-pill-toggle {
    height: auto;
  }
  .app-pill-toggle .app-pill-toggle__option {
    min-height: 44px;
  }
}
.app-pill-toggle__option:focus-visible {
  /* No offset, so the whole ring sits on the track rather than past it. */
  outline: 2px solid rgb(var(--v-theme-on-primary));
  outline-offset: 0;
}
</style>
