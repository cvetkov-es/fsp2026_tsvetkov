import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { errorText } from '../../api/errors'
import { FORMAT_TITLE, type Format } from '../../api/employer'
import { APPLICATION_STATUS, applyVacancy, getApplications, getVacancies, salary, type Vacancy } from '../../api/vacancies'
import LoadError from '../../components/LoadError'
import { Button, Card } from '../../components/ui'

type ConsentText = { type: string; title: string; body: string }

function ApplyForm({ v, onDone }: { v: Vacancy; onDone: () => void }) {
  const texts = useQuery({ queryKey: ['consent-texts'], queryFn: () => api<{ texts: ConsentText[] }>('/consents/texts') })
  const consent = texts.data?.texts.find((t) => t.type === 'contact_transfer')
  const [agree, setAgree] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  return (
    <div className="mt-3 space-y-2 text-sm">
      <textarea aria-label="Сообщение работодателю" className="w-full rounded-lg border border-line-strong px-3 py-2" rows={2} maxLength={1000}
        placeholder="Что вас заинтересовало (необязательно)" value={message} onChange={(e) => setMessage(e.target.value)} />
      <div className="rounded-lg bg-surface-2 p-3">
        <label className="flex gap-2"><input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
          <span>{consent ? consent.title : 'Согласие на передачу контактов компании'}: передать ФИО и контакты компании «{v.company.name}», если она примет отклик</span></label>
        {consent && <details className="mt-1 text-xs text-muted"><summary>Текст согласия</summary>{consent.body}</details>}
      </div>
      <Button disabled={!agree || busy} onClick={async () => {
        setError(null)
        setBusy(true)
        try { await applyVacancy(v.id, { consent_contact_transfer: true, message }); onDone() } catch (e) { setError(errorText(e)) } finally { setBusy(false) }
      }}>Откликнуться</Button>
      {error && <p role="alert" className="text-danger">{error}</p>}
    </div>
  )
}

function VacancyCard({ v, onDone }: { v: Vacancy; onDone: () => void }) {
  return (
    <Card>
      <h2 className="text-lg font-semibold">{v.title}</h2>
      <p className="text-sm text-muted">{`${v.company.name} · уровень ${v.company.trust_level}${v.company.industry ? ` · ${v.company.industry}` : ''}`}</p>
      <p className="mt-1 font-semibold">{salary(v)}</p>
      <p className="text-xs text-muted">{[v.city, v.formats.map((f) => FORMAT_TITLE[f as Format] ?? f).join(', ')].filter(Boolean).join(' · ')}</p>
      <p className="mt-2 whitespace-pre-line text-sm">{v.description}</p>
      {v.my_application
        ? <p className="mt-3 text-sm font-semibold">{`Ваш отклик: ${APPLICATION_STATUS[v.my_application.status] ?? v.my_application.status}`}</p>
        : <ApplyForm v={v} onDone={onDone} />}
    </Card>
  )
}

/** Вакансии и отклики (процесс 4.8): отклик — это согласие №4, принятый отклик становится контактом с чатом. */
export default function VacanciesPage() {
  const qc = useQueryClient()
  const list = useQuery({ queryKey: ['vacancies'], queryFn: () => getVacancies() })
  const mine = useQuery({ queryKey: ['my-applications'], queryFn: getApplications })
  const reload = () => { void qc.invalidateQueries({ queryKey: ['vacancies'] }); void qc.invalidateQueries({ queryKey: ['my-applications'] }) }
  return (
    <div className="space-y-4 p-6">
      <h1 className="text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">Вакансии</h1>
      {list.isError && <LoadError error={list.error} />}
      {list.data?.length === 0 && <Card><p>Открытых вакансий пока нет.</p></Card>}
      {list.data?.map((v) => <VacancyCard key={v.id} v={v} onDone={reload} />)}
      <h2 className="pt-2 text-lg font-semibold">Мои отклики</h2>
      {mine.isError && <LoadError error={mine.error} />}
      {mine.data?.length === 0 && <p className="text-sm text-muted">Вы ещё не откликались.</p>}
      {mine.data?.map((a) => (
        <Card key={a.id}>
          <p className="font-semibold">{a.vacancy.title}</p>
          <p className="text-sm text-muted">{a.vacancy.company.name}</p>
          <p className="mt-1 text-sm">{APPLICATION_STATUS[a.status] ?? a.status}</p>
          {a.status === 'accepted' && a.contact_id && <Link to={`/contacts/${a.contact_id}`} className="mt-1 inline-block text-sm font-semibold text-primary hover:underline">Контакты и чат</Link>}
        </Card>
      ))}
    </div>
  )
}
