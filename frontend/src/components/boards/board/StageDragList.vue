<!--
 * Copyright 2025-2026 Arun Rajkumar
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 -->

<!-- One stage's cards as a drag-and-drop list, shared by team boards and
     Delivery (useCardDrag). Each item carries ``data-card-id`` (leave it
     off and the item can't be picked up); the list carries the stage in
     ``data-stage-id``. A drop is reported as ``drop``; letting go over a
     stage the card can't enter (``dragBlocks``) as ``blocked``. -->
<script lang="ts">
import { defineComponent, h, type PropType } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import {
  blockedLanding, dragEnded, dragMoved, dragOptions, dragStarted, dropFromDragEnd, type CardDrop,
} from '@/composables/useCardDrag'

export default defineComponent({
  name: 'StageDragList',
  props: {
    /** The cards shown; the drag never edits it, the board moves cards itself. */
    items: { type: Array as PropType<unknown[]>, required: true },
    stageId: { type: String, required: true },
    /** Cards drag between lists of the same group: one board's stages. */
    group: { type: String, required: true },
    enabled: { type: Boolean, required: true },
  },
  emits: {
    drop: (_drop: CardDrop) => true,
    blocked: (_cardId: string, _stageId: string) => true,
  },
  setup(props, { slots, emit }) {
    function onEnd(event: Parameters<typeof dropFromDragEnd>[0]): void {
      // Let go over a stage it can't enter: SortableJS would drop it in the last
      // column it passed through, so that drop is cancelled and the reason given.
      const blocked = blockedLanding()
      dragEnded()
      const drop = dropFromDragEnd(event)
      if (blocked) emit('blocked', blocked.cardId, blocked.stageId)
      else if (drop) emit('drop', drop)
    }

    // The cards' slot goes to VueDraggable as it is, not re-rendered through
    // <slot>. A re-rendered slot is wrapped in a fragment, and when a stage's
    // last card leaves, Vue clears that fragment between its anchors; the
    // card SortableJS has just put back sits after them, so it stayed on
    // screen, shown twice.
    return () =>
      h(
        VueDraggable,
        {
          modelValue: props.items,
          ...dragOptions(props.group, props.enabled),
          'data-stage-id': props.stageId,
          onStart: dragStarted,
          onMove: dragMoved,
          onEnd,
        },
        { default: slots.default },
      )
  },
})
</script>
