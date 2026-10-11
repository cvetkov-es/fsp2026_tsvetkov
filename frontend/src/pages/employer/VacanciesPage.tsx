import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { errorText } from '../../api/errors'
import { listNeeds } from '../../api/employer'
import {
  acceptApplication, APPLICATION_DECLINE, APPLICATION_STATUS, closeVacancy, declineApplication, getCompanyVacancies, getVacancyApplications,
  publishVacancy, salary, type DeclineReason, type Vacancy, type VacancyApplication,
} from '../../api/vacancies'
import { CandidateCard } from '../../components/employer/CandidateCard'
import LoadError from '../../components/LoadError'
import { Button, Card } from '../../components/ui'

function ApplicationRow({ a, needId, onChanged }: { a: VacancyApplication; needId: string; onChanged: () => void }) {
  const [reason, setReason] = useState<DeclineReason>('stack')
  const [contactId, setContactId] = useState<string | null>(a.contact_id)
  const [hours, setHours] = useState('')
  const cap = a.minor_hours_limit ?? null
  const hoursNum = Number(hours)
  const hoursOk = cap === null || (hoursNum > 0 && hoursNum <= cap)
  const [error, setError] = useState<string | null>(null)
  const run = async (f: () => Promise<void>) => { setError(null); try { await f() } catch (e) { setError(errorText(e)) } }
  const open = !contactId && a.status !== 'declined'
  return (
    <li className="space-y-2 rounded-xl border border-line p-3">
      {a.card ? <CandidateCard card={a.card} needId={needId} /> : <p className="font-mono font-semibold">{a.alias}</p>}
      {a.message && <p className="text-sm">{a.message}</p>}
      <p className="text-xs text-muted">{`${APPLICATION_STATUS[contactId ? 'accepted' : a.status] ?? a.status}${a.decline_reason ? ` · ${APPLICATION_DECLINE[a.decline_reason as DeclineReason] ?? a.decline_reason}` : ''}`}</p>
      {contactId && <Link to={`/contacts/${contactId}`} className="text-sm font-semibold text-primary hover:underline">Контакты и чат</Link>}
      {open && (
        <div className="flex flex-wrap items-center gap-3 text-sm">
          {cap !== null && (
            <label className="flex items-center gap-1 text-xs">{`Часов в неделю (до ${cap})`}
              <input aria-label={`Часов в неделю (до ${cap})`} inputMode="numeric" className="w-16 rounded border border-line-strong px-1 py-0.5"
                value={hours} onChange={(e) => setHours(e.target.value.replace(/\D/g, ''))} />
            </label>
          )}
          <Button type="button" disabled={!hoursOk} onClick={() => run(async () => { setContactId((await acceptApplication(a.id, cap === null ? undefined : hoursNum)).contact_id); onChanged() })}>Принять</Button>
          <select aria-label="Причина отказа" className="rounded border border-line-strong px-2 py-1" value={reason} onChange={(e) => setReason(e.target.value as DeclineReason)}>
            {(Object.keys(APPLICATION_DECLINE) as DeclineReason[]).map((r) => <option key={r} value={r}>{APPLICATION_DECLINE[r]}</option>)}
          </select>
          <button className="text-danger hover:underline" onClick={() => void run(async () => { await declineApplication(a.id, reason); onChanged() })}>Отклонить</button>
        </div>
      )}
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
    </li>
  )
}

function Applications({ v, onChanged }: { v: Vacancy; onChanged: () => void }) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['vacancy-applications', v.id], queryFn: () => getVacancyApplications(v.id) })
  if (!q.data) return <p className="mt-2 text-sm">Загрузка…</p>
  const reload = () => { void qc.invalidateQueries({ queryKey: ['vacancy-applications', v.id] }); onChanged() }
  return (
    <ul className="mt-3 space-y-2">
      {q.data.length === 0 && <li className="text-sm text-muted">Откликов пока нет.</li>}
      {q.data.map((a) => <ApplicationRow key={a.id} a={a} needId={v.need_id} onChanged={reload} />)}
    </ul>
  )
}

function PublishForm({ vacancies, onPublished }: { vacancies: Vacancy[]; onPublished: () => void }) {
  const needs = useQuery({ queryKey: ['needs'], queryFn: listNeeds })
  const used = new Set(vacancies.map((v) => v.need_id))
  const free = needs.data?.filter((n) => n.status === 'active' && !used.has(n.id)) ?? []
  const [needId, setNeedId] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const chosen = needId && free.some((n) => n.id === needId) ? needId : (free[0]?.id ?? '')
  if (free.length === 0) return <Card><p className="text-sm">Все активные потребности уже опубликованы. Создайте новую, чтобы опубликовать вакансию.</p></Card>
  return (
    <Card>
      <h2 className="mb-2 font-semibold">Опубликовать вакансию</h2>
      <div className="space-y-3">
        <select aria-label="Потребность для вакансии" className="w-full rounded-lg border border-line-strong px-3 py-2" value={chosen} onChange={(e) => setNeedId(e.target.value)}>
          {free.map((n) => <option key={n.id} value={n.id}>{n.title}</option>)}
        </select>
        <p className="text-xs text-muted">Вилка и формат берутся из потребности. Без вилки вакансию не опубликовать.</p>
        <textarea aria-label="Описание вакансии" rows={4} className="w-full rounded-lg border border-line-strong p-2 text-sm" value={description} onChange={(e) => setDescription(e.target.value)} />
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        <Button disabled={description.trim().length < 10} onClick={async () => {
          setError(null)
          try { await publishVacancy(chosen, description); setDescription(''); onPublished() } catch (e) { setError(errorText(e)) }
        }}>Опубликовать вакансию</Button>
      </div>
    </Card>
  )
}

/** Вакансии и отклики (процесс 4.8): отклик под псевдонимом, ПДн — только после принятия и согласия №4. */
export default function VacanciesPage() {
  const qc = useQueryClient()
  const list = useQuery({ queryKey: ['company-vacancies'], queryFn: getCompanyVacancies })
  const [open, setOpen] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const reload = () => { void qc.invalidateQueries({ queryKey: ['company-vacancies'] }) }
  return (
    <div className="space-y-4 p-6">
      <h1 className="text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">Вакансии</h1>
      {list.isError && <LoadError error={list.error} />}
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {list.data && <PublishForm vacancies={list.data} onPublished={reload} />}
      {list.data?.map((v) => (
        <Card key={v.id}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold">{v.title}</h2>
            <span className="text-xs text-muted">{v.status === 'open' ? 'открыта' : 'закрыта'}</span>
          </div>
          <p className="text-sm">{salary(v)}</p>
          <div className="mt-2 flex gap-4 text-sm">
            <button className="font-semibold text-primary hover:underline" onClick={() => setOpen(open === v.id ? null : v.id)}>Отклики</button>
            {v.status === 'open' && <button className="text-muted underline" onClick={async () => { setError(null); try { await closeVacancy(v.id); reload() } catch (e) { setError(errorText(e)) } }}>Закрыть</button>}
          </div>
          {open === v.id && <Applications v={v} onChanged={reload} />}
        </Card>
      ))}
    </div>
  )
}
