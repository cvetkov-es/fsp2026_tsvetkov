import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { errorText } from '../api/errors'
import { acceptGuardian, getGuardianPage } from '../api/junior'
import LoadError from '../components/LoadError'
import { Button, Card, Field, Input } from '../components/ui'

/** Публичная страница законного представителя (процесс 2.10): текст согласия и ФИО; вход в систему не нужен. */
export default function GuardianPage() {
  const { token = '' } = useParams()
  const q = useQuery({ queryKey: ['guardian', token], queryFn: () => getGuardianPage(token), retry: false })
  const [name, setName] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (q.isError) return <div className="mx-auto max-w-2xl p-6"><LoadError error={q.error} /></div>
  if (!q.data) return <p className="p-6">Загрузка…</p>
  return (
    <div className="mx-auto max-w-2xl p-6"><Card>
      <h1 className="text-lg font-semibold">{q.data.title}</h1>
      <p className="mt-1 text-sm text-muted">{`Профиль кандидата: ${q.data.candidate_email}`}</p>
      <p className="mt-3 whitespace-pre-line text-sm">{q.data.body}</p>
      {done ? <p className="mt-4 font-semibold">Спасибо, согласие получено. Теперь работодатели могут пригласить кандидата на стажировку или каникулярную работу.</p> : (
        <div className="mt-4 space-y-3">
          <Field label="ФИО законного представителя" htmlFor="gname"><Input id="gname" aria-label="ФИО законного представителя" value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Button disabled={busy || name.trim().length < 3} onClick={async () => {
            setError(null)
            setBusy(true)
            try { await acceptGuardian(token, name.trim()); setDone(true) } catch (e) { setError(errorText(e)) } finally { setBusy(false) }
          }}>Даю согласие</Button>
          {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        </div>
      )}
    </Card></div>
  )
}
