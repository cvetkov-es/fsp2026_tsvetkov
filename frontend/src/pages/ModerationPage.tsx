import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Fragment, useState } from 'react'
import { ApiError } from '../api/client'
import { errorText } from '../api/errors'
import { getCases, resolveCase, type ModerationCase } from '../api/moderation'
import { Button, Card } from '../components/ui'

const day = (iso: string) => new Date(iso).toLocaleDateString('ru-RU')

function CaseCard({ c, onDone }: { c: ModerationCase; onDone: () => void }) {
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const act = async (action: string) => {
    setError(null)
    setBusy(true)
    try { await resolveCase(c.id, action, text); onDone() } catch (e) { setError(errorText(e)) } finally { setBusy(false) }
  }
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{c.type_title}</h2>
        <span className="text-xs text-muted">{day(c.created_at)}</span>
      </div>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        {c.summary.map((s) => (<Fragment key={s.label}><dt className="text-muted">{s.label}</dt><dd className="whitespace-pre-line">{s.value}</dd></Fragment>))}
      </dl>
      {c.comment && <p className="mt-1 text-sm">{`Комментарий автора: «${c.comment}»`}</p>}
      {c.due_at && <p className="mt-1 text-sm font-semibold text-danger">{`Ответить до ${day(c.due_at)}`}</p>}
      <textarea aria-label="Комментарий к решению" maxLength={1000} className="mt-2 w-full rounded-lg border border-line-strong p-2 text-sm" rows={2} value={text} onChange={(e) => setText(e.target.value)} />
      <div className="mt-2 flex flex-wrap gap-3">
        {c.actions.map((a, i) => i === 0
          ? <Button key={a.code} disabled={busy} onClick={() => void act(a.code)}>{a.title}</Button>
          : <button key={a.code} disabled={busy} className="text-sm text-primary hover:underline disabled:opacity-40" onClick={() => void act(a.code)}>{a.title}</button>)}
      </div>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
    </Card>
  )
}

/** Модерация — одна очередь (процесс 7): карточку и кнопки каждого обращения описывает его тип на сервере. */
export default function ModerationPage() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['cases'], queryFn: () => getCases('open') })
  return (
    <div className="space-y-4 p-6">
      <h1 className="text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">Модерация</h1>
      {q.isPending && <p>Загрузка…</p>}
      {q.isError && <p role="alert" className="text-danger">{q.error instanceof ApiError ? q.error.title : 'Не удалось загрузить обращения'}</p>}
      {q.data?.length === 0 && <Card><p>Открытых обращений нет.</p></Card>}
      {q.data?.map((c) => <CaseCard key={c.id} c={c} onDone={() => void qc.invalidateQueries({ queryKey: ['cases'] })} />)}
    </div>
  )
}
