import { useState } from 'react'
import { errorText } from '../../api/errors'
import { objectToDecision } from '../../api/complaints'
import { Button, ErrorText, Textarea } from '../ui'
import { linkClass } from '../ui-classes'

const shortDay = (iso: string) => new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })

/** Возражение против решения, принятого автоматически (ст. 16 152-ФЗ): ответ модератора — в «Моих обращениях». */
export default function ObjectionForm({ attemptId }: { attemptId: string }) {
  const [open, setOpen] = useState(false)
  const [comment, setComment] = useState('')
  const [dueAt, setDueAt] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (dueAt) return <p className="mt-3">{`Ответим до ${shortDay(dueAt)} в разделе «Мои обращения»`}</p>
  if (!open) return <button type="button" className={`mt-3 ${linkClass}`} onClick={() => setOpen(true)}>Возразить против автоматического решения (ст. 16 152-ФЗ)</button>
  return (
    <div className="mt-3 space-y-2">
      <Textarea aria-label="Почему вы не согласны с решением" rows={3} maxLength={2000}
        value={comment} onChange={(e) => setComment(e.target.value)} />
      <Button type="button" disabled={busy || comment.trim().length < 10} onClick={async () => {
        setError(null)
        setBusy(true)
        try { setDueAt((await objectToDecision(attemptId, comment.trim())).due_at) } catch (e) { setError(errorText(e)) } finally { setBusy(false) }
      }}>Отправить возражение</Button>
      <ErrorText>{error}</ErrorText>
    </div>
  )
}
