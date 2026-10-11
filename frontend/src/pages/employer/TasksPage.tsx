import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { errorText } from '../../api/errors'
import { getCompany, listNeeds, SPEC_TITLE } from '../../api/employer'
import {
  createTask, evaluateSubmission, getCompanyTasks, getTaskLimits, getTaskSubmissions, HINT_FITS, hintSubmission, inviteAuthor,
  TASK_STATUS, type CompanyTask, type Submission,
} from '../../api/tasks'
import { InviteForm } from '../../components/employer/InviteForm'
import LoadError from '../../components/LoadError'
import { Button, Card, Field, Input } from '../../components/ui'

const TRUSTED = ['L1', 'L2', 'L3']
const day = (iso: string) => new Date(iso).toLocaleDateString('ru-RU')
const ymd = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

/** Срок — конец выбранного дня, поэтому последний допустимый день на один меньше предела в днях. */
function deadlineRange(ttlDays: number): [string, string] {
  const now = Date.now()
  return [ymd(new Date(now)), ymd(new Date(now + (ttlDays - 1) * 86_400_000))]
}

function CreateForm({ onCreated }: { onCreated: () => void }) {
  const limits = useQuery({ queryKey: ['task-limits'], queryFn: getTaskLimits })
  const [title, setTitle] = useState('')
  const [spec, setSpec] = useState<'backend' | 'frontend' | 'data'>('backend')
  const [text, setText] = useState('')
  const [date, setDate] = useState('')
  const [reference, setReference] = useState('')
  const [kind, setKind] = useState<'number' | 'text'>('number')
  const [error, setError] = useState<string | null>(null)
  const [first, last] = deadlineRange(limits.data?.ttl_days ?? 1)
  return (
    <Card>
      <h2 className="mb-2 font-semibold">Новая задача</h2>
      <form className="space-y-3" onSubmit={async (e) => {
        e.preventDefault(); setError(null)
        try {
          await createTask({
            title, specialization: spec, text, deadline: new Date(`${date}T23:59:59`).toISOString(),
            ...(reference.trim() ? { reference_answer: reference.trim(), answer_kind: kind } : {}),
          })
          setTitle(''); setText(''); setDate(''); setReference('')
          onCreated()
        } catch (err) { setError(errorText(err)) }
      }}>
        <Field label="Название" htmlFor="task-title"><Input id="task-title" aria-label="Название задачи" maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Направление" htmlFor="task-spec">
            <select id="task-spec" className="w-full rounded-lg border border-line-strong px-3 py-2" value={spec} onChange={(e) => setSpec(e.target.value as typeof spec)}>
              {(Object.keys(SPEC_TITLE) as (keyof typeof SPEC_TITLE)[]).map((s) => <option key={s} value={s}>{SPEC_TITLE[s]}</option>)}
            </select>
          </Field>
          <Field label="Срок решения" htmlFor="task-deadline">
            <input id="task-deadline" aria-label="Срок" type="date" className="w-full rounded-lg border border-line-strong px-3 py-2"
              min={first} max={limits.data ? last : undefined} value={date} onChange={(e) => setDate(e.target.value)} />
          </Field>
        </div>
        <Field label="Текст задачи" htmlFor="task-text">
          <textarea id="task-text" aria-label="Текст задачи" rows={5} className="w-full rounded-lg border border-line-strong p-2 text-sm"
            maxLength={limits.data?.text_max} value={text} onChange={(e) => setText(e.target.value)} />
        </Field>
        {limits.data && <p className="text-xs text-muted">{`${text.length} / ${limits.data.text_max}`}</p>}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Эталонный ответ (необязательно, для автопроверки)" htmlFor="task-ref">
            <Input id="task-ref" maxLength={500} value={reference} onChange={(e) => setReference(e.target.value)} />
          </Field>
          <Field label="Как сравнивать с эталоном" htmlFor="task-kind">
            <select id="task-kind" className="w-full rounded-lg border border-line-strong px-3 py-2" value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
              <option value="number">число</option><option value="text">текст</option>
            </select>
          </Field>
        </div>
        <p className="text-xs text-muted">Задача должна проверять навык. Если она похожа на бесплатную работу, кандидаты могут пожаловаться, и модератор её снимет.</p>
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        <Button type="submit" disabled={title.trim().length < 3 || text.trim().length < 10 || !date}>Опубликовать задачу</Button>
      </form>
    </Card>
  )
}

function SubmissionRow({ s, reference, onChanged }: { s: Submission; reference: string | null; onChanged: () => void }) {
  const [comment, setComment] = useState('')
  const [hint, setHint] = useState(s.llm_hint)
  const [inviteNeed, setInviteNeed] = useState<string | null>(null)
  const [invited, setInvited] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const needs = useQuery({ queryKey: ['needs'], queryFn: listNeeds, enabled: inviteNeed !== null })
  const run = async (f: () => Promise<unknown>) => { setError(null); try { await f() } catch (e) { setError(errorText(e)) } }
  const auto = s.auto_correct === null ? null : s.auto_correct ? 'совпадает с эталоном' : 'не совпадает с эталоном'
  return (
    <li className="rounded-xl border border-line p-3">
      <p className="font-mono font-semibold">{s.alias}</p>
      <p className="mt-1 whitespace-pre-line text-sm">{s.answer}</p>
      {auto && <p className="text-xs text-muted">{`Автопроверка: ${auto}${reference ? ` (эталон: ${reference})` : ''}`}</p>}
      {s.verdict && <p className="text-sm font-semibold">{`Решение: ${s.verdict === 'accepted' ? 'принято' : 'не принято'}${s.comment ? ` · ${s.comment}` : ''}`}</p>}
      {hint && (
        <p className="mt-1 rounded-lg bg-surface-2 p-2 text-sm">
          {`${HINT_FITS[hint.fits] ?? hint.fits}: ${hint.summary}`}<br /><span className="text-xs text-muted">подсказка ИИ, решаете вы</span>
        </p>
      )}
      {!s.verdict && (
        <div className="mt-2 space-y-2">
          <Input aria-label="Комментарий к решению" placeholder="Комментарий кандидату (необязательно)" maxLength={1000} value={comment} onChange={(e) => setComment(e.target.value)} />
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <Button type="button" onClick={() => run(async () => { await evaluateSubmission(s.id, { verdict: 'accepted', comment }); onChanged() })}>Принять</Button>
            <button className="text-danger hover:underline" onClick={() => void run(async () => { await evaluateSubmission(s.id, { verdict: 'rejected', comment }); onChanged() })}>Не принять</button>
            <button className="text-primary hover:underline" onClick={() => void run(async () => { setHint((await hintSubmission(s.id)).llm_hint) })}>Подсказка ИИ</button>
          </div>
        </div>
      )}
      <div className="mt-2 text-sm">
        {invited ? <p className="text-muted">Приглашение автору отправлено.</p>
          : inviteNeed === null ? <button className="font-semibold text-primary hover:underline" onClick={() => setInviteNeed('')}>Пригласить автора</button>
          : (
            <div className="space-y-2">
              <select aria-label="Потребность для приглашения" className="rounded border border-line-strong px-2 py-1" value={inviteNeed} onChange={(e) => setInviteNeed(e.target.value)}>
                <option value="">Выберите потребность</option>
                {needs.data?.filter((n) => n.status === 'active').map((n) => <option key={n.id} value={n.id}>{n.title}</option>)}
              </select>
              {inviteNeed && <InviteForm needId={inviteNeed} cardRef={s.ref} onSent={() => setInvited(true)} send={(v) => inviteAuthor(s.id, { ...v, need_id: inviteNeed })} />}
            </div>
          )}
      </div>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
    </li>
  )
}

function Submissions({ task, onChanged }: { task: CompanyTask; onChanged: () => void }) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['task-submissions', task.id], queryFn: () => getTaskSubmissions(task.id) })
  if (!q.data) return <p className="mt-2 text-sm">Загрузка…</p>
  const reload = () => { void qc.invalidateQueries({ queryKey: ['task-submissions', task.id] }); onChanged() }
  return (
    <ul className="mt-3 space-y-2">
      {q.data.items.length === 0 && <li className="text-sm text-muted">Решений пока нет.</li>}
      {q.data.items.map((s) => <SubmissionRow key={s.id} s={s} reference={q.data.task.reference_answer} onChanged={reload} />)}
    </ul>
  )
}

/** Задачи работодателя (процесс 4.6): публикация с L1, решения псевдонимны, ИИ только советует. */
export default function TasksPage() {
  const qc = useQueryClient()
  const company = useQuery({ queryKey: ['company'], queryFn: getCompany })
  const tasks = useQuery({ queryKey: ['company-tasks'], queryFn: getCompanyTasks })
  const [open, setOpen] = useState<string | null>(null)
  const reload = () => { void qc.invalidateQueries({ queryKey: ['company-tasks'] }) }
  const canPublish = !!company.data && TRUSTED.includes(company.data.trust_level)
  return (
    <div className="space-y-4 p-6">
      <h1 className="text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">Задачи</h1>
      {company.data && !canPublish && (
        <Card><p>Публиковать задачи можно с уровня доверия L1 (корпоративный домен). Сейчас у компании уровень {company.data.trust_level}.</p></Card>
      )}
      {canPublish && <CreateForm onCreated={reload} />}
      {tasks.isError && <LoadError error={tasks.error} />}
      {tasks.data?.length === 0 && <Card><p>Задач пока нет.</p></Card>}
      {tasks.data?.map((t) => (
        <Card key={t.id}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold">{t.title}</h2>
            <span className="text-xs text-muted">{`${TASK_STATUS[t.status] ?? t.status} · до ${day(t.deadline)}`}</span>
          </div>
          <button className="mt-2 text-sm font-semibold text-primary hover:underline" onClick={() => setOpen(open === t.id ? null : t.id)}>
            {`Решения (${t.submissions}, ждут проверки: ${t.pending})`}
          </button>
          {open === t.id && <Submissions task={t} onChanged={reload} />}
        </Card>
      ))}
    </div>
  )
}
