import { useState } from 'react'
import { errorText } from '../../api/errors'
import { ITEM_REASON_TITLE, reportItem, type ItemReason } from '../../api/complaints'
import { Button, ErrorText, Select, Textarea } from '../ui'

/** «Сообщить о проблеме в задании»: обращение модератору. Форма не трогает ответ и таймер задания. */
export default function ReportItem({ attemptId, seq }: { attemptId: string; seq: number }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState<ItemReason>('wrong_key')
  const [comment, setComment] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (done) return <p className="mt-4 text-sm text-muted">Спасибо, модератор проверит</p>
  if (!open) return <button type="button" className="mt-4 text-xs text-muted underline hover:text-ink" onClick={() => setOpen(true)}>Сообщить о проблеме в задании</button>
  return (
    <div className="mt-4 space-y-2 rounded-xl border border-line p-3 text-sm">
      <label className="flex flex-wrap items-center gap-2">Что не так
        <Select aria-label="Что не так" className="w-auto!" value={reason} onChange={(e) => setReason(e.target.value as ItemReason)}>
          {(Object.keys(ITEM_REASON_TITLE) as ItemReason[]).map((r) => <option key={r} value={r}>{ITEM_REASON_TITLE[r]}</option>)}
        </Select>
      </label>
      <Textarea aria-label="Комментарий" rows={2} maxLength={1000}
        placeholder="Комментарий (необязательно)" value={comment} onChange={(e) => setComment(e.target.value)} />
      <Button type="button" disabled={busy} onClick={async () => {
        setError(null)
        setBusy(true)
        try { await reportItem(attemptId, seq, { reason, comment }); setDone(true) } catch (e) { setError(errorText(e)) } finally { setBusy(false) }
      }}>Отправить</Button>
      <ErrorText>{error}</ErrorText>
    </div>
  )
}
