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

// Follow one socket topic whose messages carry an ``event`` name, routing
// each message to the handler for its event. Events published while the
// socket was down aren't replayed, so ``onResync`` runs on every
// reconnect for the caller to refetch what it shows.
//
// The topic can change (or be unknown until a load finishes): pass a ref
// or getter and the channel follows it, dropping the previous topic.
// With ``ignoreOwn``, messages whose ``origin`` is this tab's client id
// (the echo of a change this tab made) are skipped.

import { getCurrentScope, onScopeDispose, toValue, watch, type MaybeRefOrGetter } from 'vue'
import { clientId } from '@/services/clientId'
import { subscribe, unsubscribe } from '@/services/socket'
import { onSocketReconnect } from '@/services/wsReconnect'

export interface TopicMessage {
  event: string
  /** The client id of the tab whose change this announces, when there is one. */
  origin?: string | null
}

export interface TopicChannelOptions {
  /** Skip messages this tab caused (their ``origin`` is our client id). */
  ignoreOwn?: boolean
}

/** One optional handler per event name, typed by that event's message. */
export type TopicHandlers<E extends TopicMessage> = {
  [K in E['event']]?: (message: Extract<E, { event: K }>) => void
}

function isMessage(data: unknown): data is TopicMessage {
  return typeof data === 'object' && data !== null && typeof (data as TopicMessage).event === 'string'
}

export function useTopicChannel<E extends TopicMessage>(
  topic: MaybeRefOrGetter<string | null>,
  handlers: TopicHandlers<E>,
  onResync: () => void,
  options: TopicChannelOptions = {},
) {
  let cleanup: (() => void) | null = null

  function stop(): void {
    cleanup?.()
    cleanup = null
  }

  function start(name: string): void {
    const onMessage = (data: unknown) => {
      if (!isMessage(data)) return
      if (options.ignoreOwn && data.origin === clientId) return
      const handler = handlers[data.event as E['event']] as ((m: E) => void) | undefined
      handler?.(data as E)
    }
    subscribe(name, onMessage)
    const unregister = onSocketReconnect(onResync)
    cleanup = () => {
      unsubscribe(name, onMessage)
      unregister()
    }
  }

  const stopWatch = watch(
    () => toValue(topic),
    name => {
      stop()
      if (name) start(name)
    },
    { immediate: true },
  )

  function dispose(): void {
    stopWatch()
    stop()
  }

  if (getCurrentScope()) onScopeDispose(dispose)
  return { dispose }
}
