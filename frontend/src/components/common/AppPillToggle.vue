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
     times. An option with ``disabled: true`` stays in view but can't be
     picked (click or arrow keys); say why beside the toggle. -->
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
      :aria-disabled="opt.disabled || undefined"
      :disabled="opt.disabled"
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
  /** Shown but not pickable. */
  disabled?: boolean
}

interface Props {
  modelValue: T
  options: PillOption<T>[]
  // When true (default), clicking the already-active option does
  // nothing — the parent always sees a non-null model value.
  mandatory?: boolean
  // ``md`` (default) matches the v-tabs density="compact" height
  // (34px). ``sm`` is for tight chrome (e.g. card headers). ``touch``
  // is for a row of many options that scrolls sideways (phone tabs):
  // separate 44px pills, the picked one filled, rather than one track.
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

const enabled = (index: number) => !props.options[index]?.disabled

/** The next pickable option from ``from`` in ``step`` direction, or -1 when there's none. */
function nextEnabled(from: number, step: number): number {
  const count = props.options.length
  for (let i = 1; i <= count; i++) {
    const at = (from + step * i + count * count) % count
    if (enabled(at)) return at
  }
  return -1
}

function onKey(event: KeyboardEvent): void {
  const count = props.options.length
  const at = props.options.findIndex(o => o.value === focusValue.value)
  let next: number
  if (event.key in STEPS) next = nextEnabled(at, STEPS[event.key])
  else if (event.key === 'Home') next = nextEnabled(count - 1, 1)
  else if (event.key === 'End') next = nextEnabled(0, -1)
  else return
  event.preventDefault()
  if (next < 0) return
  select(props.options[next].value)
  void nextTick(() => root.value?.querySelectorAll<HTMLElement>('[role="radio"]')[next]?.focus())
}

function select(value: T): void {
  if (props.options.find(o => o.value === value)?.disabled) return
  if (props.mandatory && value === props.modelValue) return
  emit('update:modelValue', value)
}
</script>

<style scoped src="./app-pill-toggle.css"></style>
