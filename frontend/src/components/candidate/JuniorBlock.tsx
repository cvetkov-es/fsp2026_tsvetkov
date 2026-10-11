import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { errorText } from '../../api/errors'
import { getJunior, requestGuardian } from '../../api/junior'
import LoadError from '../LoadError'
import { Button, Card, Input } from '../ui'

/** Юниорский трек (процесс 2.10): профиль 14–17 лет — черновик до согласия законного представителя. */
export default function JuniorBlock() {
  const q = useQuery({ queryKey: ['junior'], queryFn: getJunior, retry: false })
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState<{ url: string | null } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const j = q.data
  if (q.isError) return <Card><LoadError error={q.error} /></Card>  // молчание выглядело бы как «всё хорошо»
  if (!j?.minor) return null
  if (j.status === 'active') {
    return (
      <Card>
        <p className="text-sm text-muted">Юниорский трек</p>
        <p className="font-semibold">{`Доступны стажировка и каникулярная работа, до ${j.hours_limit_vacation} ч в неделю в каникулы и до ${j.hours_limit_school} ч в учебный год.`}</p>
        <p className="mt-1 text-xs text-muted">{`Согласие законного представителя получено (${j.guardian_email}).`}</p>
      </Card>
    )
  }
  return (
    <Card>
      <p className="text-sm text-muted">Юниорский трек</p>
      <p className="font-semibold">Работодатели увидят профиль после согласия законного представителя.</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <div className="w-72 max-w-full"><Input aria-label="Почта законного представителя" type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
        <Button type="button" disabled={busy || !email.includes('@')} onClick={async () => {
          setError(null)
          setBusy(true)
          try { setSent({ url: (await requestGuardian(email)).guardian_url }) } catch (e) { setError(errorText(e)) } finally { setBusy(false) }
        }}>Отправить ссылку представителю</Button>
      </div>
      {sent && <p className="mt-2 text-sm">Ссылка отправлена на почту представителя. Она действует несколько дней.</p>}
      {sent?.url && <Link to={new URL(sent.url).pathname} className="mt-1 inline-block text-sm text-primary hover:underline">Открыть страницу согласия (демо)</Link>}
      {error && <p role="alert" className="mt-2 text-sm text-danger">{error}</p>}
    </Card>
  )
}
