import { useCallback, useEffect, useRef, useState } from 'react'
import type { IntegrityEvent } from '../api/assessment'

/** Фиксирует уход со вкладки, вставку и копирование. Это только сигналы, не санкции. */
export function useIntegrity() {
  const events = useRef<IntegrityEvent[]>([])
  const [notice, setNotice] = useState(false)
  const shown = useRef(false)
  useEffect(() => {
    const push = (type: IntegrityEvent['type']) => events.current.push({ type, at: new Date().toISOString() })
    const onVis = () => {
      if (document.visibilityState === 'hidden') push('blur')
      else if (!shown.current && events.current.some((e) => e.type === 'blur')) { shown.current = true; setNotice(true) }
    }
    const onPaste = () => push('paste')
    document.addEventListener('visibilitychange', onVis)
    document.addEventListener('paste', onPaste)
    return () => { document.removeEventListener('visibilitychange', onVis); document.removeEventListener('paste', onPaste) }
  }, [])
  const take = useCallback(() => { const out = events.current; events.current = []; return out }, [])
  // Отправка не удалась — события возвращаются в начало очереди и уйдут со следующей попыткой
  const restore = useCallback((lost: IntegrityEvent[]) => { events.current = [...lost, ...events.current] }, [])
  const copy = useCallback(() => events.current.push({ type: 'copy', at: new Date().toISOString() }), [])
  return { take, restore, copy, notice, dismiss: () => setNotice(false) }
}
