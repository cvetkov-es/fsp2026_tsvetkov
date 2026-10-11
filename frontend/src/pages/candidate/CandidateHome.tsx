import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  getAvailability, getMeta, getProfile, GRADE_TITLE, listAttempts, resetCooldowns,
  type Availability, type Grade, type Profile,
} from '../../api/assessment'
import { api, ApiError } from '../../api/client'
import { getMyInvitations, type ContactStatus } from '../../api/contacts'
import { getSkills } from '../../api/skills'
import DemandBlock from '../../components/candidate/DemandBlock'
import JuniorBlock from '../../components/candidate/JuniorBlock'
import { Button, Card, Dot, ErrorText, LinkButton, Page, Pill, type PillTone } from '../../components/ui'
import { linkClass } from '../../components/ui-classes'

const GRADES: Grade[] = ['junior', 'middle', 'senior']
const AWAITING: ContactStatus[] = ['sent', 'viewed', 'offer_v2']
const day = (iso: string) => new Date(iso).toLocaleDateString('ru-RU')
const waiting = (n: number) => (n % 10 === 1 && n % 100 !== 11 ? 'приглашение ждёт ответа'
  : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? 'приглашения ждут ответа' : 'приглашений ждут ответа')

/** Какие тесты предлагать: с подтверждённым грейдом — пересдачу и грейды выше, без него — все, заявленный первым. */
function gradeOptions(p: Profile): { grade: Grade; label: string }[] {
  if (p.grade_status === 'confirmed' && p.confirmed_grade) {
    const from = GRADES.indexOf(p.confirmed_grade)
    return [
      ...GRADES.slice(from + 1).map((g) => ({ grade: g, label: `Тест на ${GRADE_TITLE[g]}` })),
      { grade: p.confirmed_grade, label: `Пересдать ${GRADE_TITLE[p.confirmed_grade]}` },
    ]
  }
  const first = p.claimed_grade ?? 'middle'
  return [first, ...GRADES.filter((g) => g !== first)].map((g, i) => ({
    grade: g, label: i === 0 ? `Пройти тест на ${GRADE_TITLE[g]}` : `Тест на ${GRADE_TITLE[g]}`,
  }))
}

function statusTitle(p: Profile): string {
  if (p.grade_status === 'confirmed' && p.confirmed_grade) return `${GRADE_TITLE[p.confirmed_grade]} подтверждён тестом`
  if (p.grade_status === 'not_confirmed') return `${GRADE_TITLE[p.status_grade ?? p.claimed_grade ?? 'middle']} не подтверждён`
  return 'Тест ещё не пройден'
}

type Step = { tag: string; tone: PillTone; option?: { label: string; primary: boolean }; locked?: string }

/** Ступень лестницы (01-candidate-home.png): статус грейда и действие, если оно сейчас доступно. */
function stepOf(p: Profile, g: Grade, options: { grade: Grade; label: string }[], av?: Availability): Step {
  const confirmed = p.grade_status === 'confirmed' ? p.confirmed_grade : null
  const i = options.findIndex((o) => o.grade === g)
  const option = i >= 0 ? { label: options[i].label, primary: i === 0 } : undefined
  const locked = option && av && !av.allowed && av.available_at ? `${option.label}: можно с ${day(av.available_at)}` : undefined
  if (confirmed === g) return { tag: 'Подтверждён', tone: 'success', option, locked }
  if (confirmed && GRADES.indexOf(g) < GRADES.indexOf(confirmed)) return { tag: 'Ниже подтверждённого', tone: 'neutral' }
  if (option?.primary) return { tag: 'Следующий шаг', tone: 'solid', option, locked }
  if (p.grade_status === 'not_confirmed' && (p.status_grade ?? p.claimed_grade) === g) return { tag: 'Не подтверждён', tone: 'neutral', option, locked }
  return { tag: 'Доступен', tone: 'neutral', option, locked }
}

function Ladder({ p, options, av, notes }: { p: Profile; options: { grade: Grade; label: string }[]; av?: Record<Grade, Availability>; notes: Partial<Record<Grade, string>> }) {
  return (
    <section aria-label="Грейды" className="grid gap-2 rounded-card border border-line bg-white p-2 md:grid-cols-3">
      {GRADES.map((g, idx) => {
        const s = stepOf(p, g, options, av?.[g])
        const next = s.tag === 'Следующий шаг'
        return (
          <div key={g} className={`flex min-h-[220px] flex-col gap-4 rounded-[14px] border p-5 sm:p-[22px] ${next ? 'border-primary-line bg-primary-tint' : 'border-line-soft bg-white'}`}>
            <div className="flex items-center justify-between">
              <Pill tone={s.tone}>{s.tag}</Pill>
              <span className="font-mono text-xs text-subtle">0{idx + 1}</span>
            </div>
            <p className="text-3xl font-semibold tracking-[-0.025em]">{GRADE_TITLE[g]}</p>
            <p className="flex-1 text-sm leading-snug text-muted">{notes[g]}</p>
            {s.locked ? <p className="text-sm text-muted">{s.locked}</p> : s.option && (
              <div className="flex flex-wrap gap-2">
                <LinkButton to={`/test/rules?grade=${g}`} variant={s.option.primary ? 'primary' : 'secondary'}>{s.option.label}</LinkButton>
                <LinkButton to={`/test/rules?grade=${g}&express=1`} variant="secondary" className="text-primary">экспресс · 3–5 минут</LinkButton>
              </div>
            )}
          </div>
        )
      })}
    </section>
  )
}

export default function CandidateHome() {
  const profile = useQuery({ queryKey: ['profile'], queryFn: getProfile })
  const meta = useQuery({ queryKey: ['meta'], queryFn: getMeta })
  const av = useQuery({ queryKey: ['availability'], queryFn: getAvailability })
  const hist = useQuery({ queryKey: ['attempts'], queryFn: listAttempts })
  // Тот же запрос, что в шапке: отвечает только в демо-режиме (жюри регистрирует свои аккаунты)
  const demo = useQuery({ queryKey: ['personas'], queryFn: () => api<unknown[]>('/demo/personas'), retry: false })
  const skills = useQuery({ queryKey: ['skills'], queryFn: getSkills })
  const invites = useQuery({ queryKey: ['my-invitations'], queryFn: getMyInvitations })
  const [error, setError] = useState<string | null>(null)
  const p = profile.data
  if (!p) return <p className="p-6">Загрузка…</p>
  if (!p.specialization) {
    return <Page narrow><Card className="space-y-3"><p>Начните с выбора направления и грейда.</p><LinkButton to="/candidate/survey">Выбрать</LinkButton></Card></Page>
  }
  const spec = meta.data?.specializations.find((s) => s.code === p.specialization)
  const options = gradeOptions(p)
  const notes = Object.fromEntries((meta.data?.grades ?? []).map((g) => [g.code, g.description])) as Partial<Record<Grade, string>>
  const rec = skills.data?.find((s) => s.recommended && s.available && s.bank_ready)  // процесс 2.5: по одному
  const awaiting = invites.data?.filter((i) => AWAITING.includes(i.status)) ?? []
  return (
    <Page>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0 flex-[1_1_420px]">
          <p className="text-sm text-muted">{spec?.title ?? 'Категория'}{p.claimed_grade ? ` · заявлен ${GRADE_TITLE[p.claimed_grade]}` : ''}</p>
          <h1 className="mt-1.5 text-3xl font-semibold leading-tight tracking-[-0.03em] sm:text-4xl">{statusTitle(p)}</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <LinkButton to="/candidate/survey" variant="secondary" size="sm">Изменить направление</LinkButton>
          <LinkButton to="/candidate/profile" variant="secondary" size="sm">Профиль и условия</LinkButton>
          {demo.isSuccess && (
            <Button variant="ghost" size="sm" onClick={async () => {
              setError(null)
              try { await resetCooldowns(); await av.refetch(); await skills.refetch() } catch (e) { setError(e instanceof ApiError ? e.title : 'Не удалось выполнить действие') }
            }}>Разрешить пересдачу сейчас (демо)</Button>
          )}
        </div>
      </div>
      <ErrorText>{error}</ErrorText>
      {spec && !spec.test_available
        ? <Card><p>Тест по направлению готовится. Можно выбрать другое направление.</p></Card>
        : <Ladder p={p} options={options} av={av.data} notes={notes} />}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card as="section" className="space-y-2">
          <h2 className="text-lg font-semibold">История тестов</h2>
          {hist.data?.length ? (
            <ul className="divide-y divide-line-soft">{hist.data.map((h) => (
              <li key={h.id} className="grid grid-cols-[12px_1fr_auto] items-center gap-3.5 py-3.5">
                <Dot tone={h.decision === 'confirmed' ? 'success' : 'neutral'} />
                <Link className="text-[15px] font-medium hover:text-primary" to={`/test/${h.id}`}>{h.phrase ?? (h.status === 'incomplete' ? `${GRADE_TITLE[h.target_grade]}: не завершён` : `${GRADE_TITLE[h.target_grade]}: в процессе`)}</Link>
                <span className="font-mono text-[13px] text-subtle">{day(h.started_at)}{h.express ? ' · экспресс' : ''}</span>
              </li>
            ))}</ul>
          ) : <p className="text-sm text-muted">Пока нет попыток.</p>}
        </Card>
        <div className="space-y-6">
          {rec && (
            <Card tone="night" as="section" className="space-y-3.5">
              <p className="text-[13px] text-night-muted">Навык по вашему стеку</p>
              <p className="text-[22px] font-semibold leading-tight tracking-[-0.02em]">{rec.title}: подтвердите {rec.techs.slice(0, 3).join(', ')} за 6 заданий</p>
              <div className="flex flex-wrap gap-2">
                <LinkButton to="/candidate/skills" variant="light">Пройти тест навыка</LinkButton>
                <LinkButton to="/candidate/skills" variant="outline-light">Все навыки</LinkButton>
              </div>
            </Card>
          )}
          <Link to="/candidate/invitations" className="flex items-center gap-4 rounded-card border border-line bg-white p-6 hover:border-primary-line">
            <span className="text-4xl font-semibold tracking-[-0.03em] text-primary">{awaiting.length}</span>
            <span className="flex-1">
              <span className="block font-semibold">{awaiting.length ? waiting(awaiting.length) : 'Приглашений пока нет'}</span>
              <span className="mt-0.5 block text-[13px] text-muted">{awaiting.length
                ? awaiting.slice(0, 2).map((i) => i.company.name).join(' и ') + (awaiting.length > 2 ? ' и другие' : '')
                : 'Держите профиль открытым для предложений'}</span>
            </span>
            <span aria-hidden="true" className="text-xl text-subtle">→</span>
          </Link>
          <Card as="section" className="space-y-2">
            <h2 className="text-lg font-semibold">Инициатива</h2>
            <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
              <Link to="/candidate/companies" className={linkClass}>Компании: «Хочу к вам»</Link>
              <Link to="/candidate/tasks" className={linkClass}>Задачи компаний</Link>
              <Link to="/candidate/vacancies" className={linkClass}>Вакансии</Link>
            </div>
          </Card>
        </div>
      </div>
      <JuniorBlock />
      <DemandBlock />
    </Page>
  )
}
