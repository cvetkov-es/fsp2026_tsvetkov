import { useEffect, useRef, useState } from 'react'

export function Timer({ seconds, onExpire }: { seconds: number; onExpire: () => void }) {
  const [left, setLeft] = useState(seconds)
  // Родитель пересоздаёт колбэк на каждый ввод: держим его в ref, чтобы отсчёт не начинался заново
  const expire = useRef(onExpire)
  useEffect(() => { expire.current = onExpire }, [onExpire])
  useEffect(() => {
    let fired = false
    const started = Date.now()
    const id = setInterval(() => {
      const rest = Math.max(0, seconds - Math.floor((Date.now() - started) / 1000))
      setLeft(rest)
      if (rest === 0 && !fired) { fired = true; expire.current() }
    }, 250)
    return () => clearInterval(id)
  }, [seconds])
  const m = Math.floor(left / 60)
  const s = String(left % 60).padStart(2, '0')
  const low = left <= 10
  return (
    <span className={`inline-flex items-center gap-2.5 rounded-[10px] px-3 py-1.5 ${low ? 'bg-danger-soft' : 'bg-canvas'}`}>
      <span aria-hidden="true" className={`size-2 rounded-full ${low ? 'bg-danger' : 'bg-primary'}`} />
      <span className={`font-mono text-[15px] font-semibold ${low ? 'text-danger' : 'text-ink'}`} aria-live="polite">{m}:{s}</span>
    </span>
  )
}
