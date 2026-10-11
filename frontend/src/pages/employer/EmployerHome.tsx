import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { GRADE_TITLE } from '../../api/assessment'
import { getCompany, listNeeds, SPEC_TITLE } from '../../api/employer'
import { getInterest } from '../../api/initiative'
import { Card, LinkButton, Page, Pill } from '../../components/ui'
import { linkClass } from '../../components/ui-classes'

const rub = (n: number) => n.toLocaleString('ru-RU')

/** Главная работодателя (06-employer-home.png): шапка компании, действия, таблица потребностей, интерес кандидатов. */
export default function EmployerHome() {
  const company = useQuery({ queryKey: ['company'], queryFn: getCompany })
  const needs = useQuery({ queryKey: ['needs'], queryFn: listNeeds, enabled: !!company.data })
  const interest = useQuery({ queryKey: ['interest'], queryFn: getInterest, enabled: !!company.data })
  if (company.isLoading) return <p className="p-6">Загрузка…</p>
  if (!company.data) {
    return <Page narrow><Card className="space-y-3"><p>Начните с профиля компании.</p><LinkButton to="/employer/company">Заполнить</LinkButton></Card></Page>
  }
  const c = company.data
  return (
    <Page>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-center gap-4">
          <span aria-hidden="true" className="grid size-14 shrink-0 place-items-center rounded-2xl bg-ink text-xl font-semibold text-white">{c.name.slice(0, 1)}</span>
          <div>
            <p className="text-sm text-muted">Компания · уровень доверия {c.trust_level}</p>
            <h1 className="mt-0.5 text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">{c.name}</h1>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <LinkButton to="/employer/map" variant="secondary">Карта категорий</LinkButton>
          <LinkButton to="/employer/teams" variant="secondary">Команды ФСП</LinkButton>
          <LinkButton to="/employer/tasks" variant="secondary">Задачи</LinkButton>
          <LinkButton to="/employer/vacancies" variant="secondary">Вакансии</LinkButton>
          <LinkButton to="/employer/needs/new">+ Новая потребность</LinkButton>
        </div>
      </div>

      <Card as="section" className="overflow-hidden p-0">
        <h2 className="sr-only">Потребности</h2>
        {needs.data?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left">
              <thead>
                <tr className="bg-surface-2 text-xs font-semibold uppercase tracking-[0.05em] text-subtle">
                  <th className="px-6 py-3.5 font-semibold">Потребность</th><th className="px-4 py-3.5 font-semibold">Грейды</th>
                  <th className="px-4 py-3.5 font-semibold">Вилка</th><th className="px-4 py-3.5 font-semibold">Статус</th><th className="w-10" />
                </tr>
              </thead>
              <tbody>{needs.data.map((n) => (
                <tr key={n.id} className={`border-t border-line-soft hover:bg-surface-2 ${n.status === 'closed' ? 'opacity-60' : ''}`}>
                  <td className="px-6 py-5">
                    <Link className="text-base font-semibold text-ink hover:text-primary" to={`/employer/needs/${n.id}`}>{n.title}</Link>
                    <p className="mt-0.5 text-[13px] text-muted">{n.must.join(', ') || SPEC_TITLE[n.specialization]}</p>
                  </td>
                  <td className="px-4 py-5 text-sm">{n.grades.map((g) => GRADE_TITLE[g]).join(', ')}</td>
                  <td className="px-4 py-5">
                    <p className="text-sm font-medium">{rub(n.salary_from)} – {rub(n.salary_to)} ₽</p>
                    <p className="mt-0.5 text-xs text-muted">{n.gross_net === 'gross' ? 'до вычета' : 'на руки'}</p>
                  </td>
                  <td className="px-4 py-5">{n.status === 'closed' ? <Pill>закрыта</Pill> : <Pill tone="success">активна</Pill>}</td>
                  <td className="pr-6 text-lg text-subtle" aria-hidden="true">→</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <p className="p-6 text-sm text-muted">Пока нет потребностей. <Link className={linkClass} to="/employer/needs/new">Создать первую</Link></p>}
      </Card>

      <Card as="section" className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Интерес к компании</h2>
          <p className="mt-1 text-[13px] text-muted">Кандидаты, отметившие «Хочу к вам», стоят выше в ваших подборках.</p>
        </div>
        {interest.data?.length ? <ul className="divide-y divide-line-soft">{interest.data.map((i) => (
          <li key={i.ref} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
            <span className="font-mono text-sm font-semibold">{i.alias}</span>
            <span className="text-[13px] text-muted">{`${SPEC_TITLE[i.specialization as keyof typeof SPEC_TITLE] ?? i.specialization}${i.grade ? ` · ${GRADE_TITLE[i.grade as keyof typeof GRADE_TITLE]}` : ''} · ${new Date(i.at).toLocaleDateString('ru-RU')}`}</span>
          </li>
        ))}</ul> : <p className="text-sm text-muted">Пока никто не отметил интерес</p>}
      </Card>
    </Page>
  )
}
