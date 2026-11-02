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

/**
 * CelebrationBurst — a brief toast with a CSS confetti burst over the
 * garden canvas. Pure DOM, no PlayCanvas and no assets: shared by the
 * takeover's SP rewards and the board-activity celebrations. The message
 * is set as text, never markup.
 */

const CONFETTI_COUNT = 30
const CONFETTI_COLORS = ['#D4A843', '#F9A825', '#66BB6A', '#42A5F5', '#EF5350', '#AB47BC']
const CONFETTI_SPREAD_X_PX = 300
const CONFETTI_RISE_MIN_PX = 100
const CONFETTI_RISE_RANGE_PX = 200
const CONFETTI_SIZE_MIN_PX = 6
const CONFETTI_SIZE_RANGE_PX = 6
const CONFETTI_MS = 1300
const TOAST_MS = 3000
const STYLE_ID = 'takeover-confetti-css'

function toastElement(message: string): HTMLElement {
  const toast = document.createElement('div')
  Object.assign(toast.style, {
    position: 'absolute', top: '80px', left: '50%',
    transform: 'translateX(-50%)',
    background: 'linear-gradient(135deg, #D4A843 0%, #F9A825 100%)',
    color: '#1a1a1a', padding: '10px 24px', borderRadius: '8px',
    fontSize: '15px', fontWeight: '700', pointerEvents: 'none',
    zIndex: '10', boxShadow: '0 4px 20px rgba(212, 168, 67, 0.5)',
    animation: 'toast-pop 0.4s ease-out',
  } as Partial<CSSStyleDeclaration>)
  toast.textContent = message
  return toast
}

function confettiPiece(): HTMLElement {
  const p = document.createElement('div')
  const x = (Math.random() - 0.5) * CONFETTI_SPREAD_X_PX
  const y = -(Math.random() * CONFETTI_RISE_RANGE_PX + CONFETTI_RISE_MIN_PX)
  const rot = Math.random() * 720
  const color = CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)]
  const size = CONFETTI_SIZE_MIN_PX + Math.random() * CONFETTI_SIZE_RANGE_PX
  Object.assign(p.style, {
    position: 'absolute', top: '50%', left: '50%',
    width: size + 'px', height: size + 'px',
    background: color, borderRadius: Math.random() > 0.5 ? '50%' : '2px',
    pointerEvents: 'none', zIndex: '9',
    animation: `confetti-burst 1.2s ease-out forwards`,
    '--cx': x + 'px', '--cy': y + 'px', '--cr': rot + 'deg',
  } as unknown as Partial<CSSStyleDeclaration>)
  return p
}

function ensureKeyframes(): void {
  if (document.getElementById(STYLE_ID)) return
  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = `
    @keyframes confetti-burst {
      0% { transform: translate(0, 0) rotate(0deg); opacity: 1; }
      100% { transform: translate(var(--cx), var(--cy)) rotate(var(--cr)); opacity: 0; }
    }
    @keyframes toast-pop {
      0% { transform: translateX(-50%) scale(0.5); opacity: 0; }
      100% { transform: translateX(-50%) scale(1); opacity: 1; }
    }
  `
  document.head.appendChild(style)
}

/** Show ``message`` as a toast with confetti inside ``container`` (a positioned element). */
export function showCelebration(container: HTMLElement, message: string): void {
  const toast = toastElement(message)
  container.appendChild(toast)
  for (let i = 0; i < CONFETTI_COUNT; i++) {
    const p = confettiPiece()
    container.appendChild(p)
    setTimeout(() => p.remove(), CONFETTI_MS)
  }
  ensureKeyframes()
  setTimeout(() => toast.remove(), TOAST_MS)
}
