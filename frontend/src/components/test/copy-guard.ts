import type { ClipboardEvent } from 'react'

/** Копирование заданий запрещено (кроме «Работы с ИИ»): попытка — сигнал честности, без санкций. */
export const copyGuard = (allowCopy: boolean, onCopyAttempt?: () => void) => (e: ClipboardEvent<HTMLElement>) => {
  if (allowCopy) return
  e.preventDefault()
  onCopyAttempt?.()
}
