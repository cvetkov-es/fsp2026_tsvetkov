import type { ReactNode } from 'react'
import { GRADE_TITLE, type AttemptState, type Grade } from '../../api/assessment'
import ObjectionForm from '../../components/candidate/ObjectionForm'
import { Dot, LinkButton, Meter, Notice, Page, Stat, StatGrid } from '../../components/ui'
import { linkClass } from '../../components/ui-classes'

const NEXT: Record<Grade, Grade | null> = { junior: 'middle', middle: 'senior', senior: null }
const pct = (v: number) => `${Math.round(v * 100)}%`
const days = (n: number) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? 'день' : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? 'дня' : 'дней'}`

/** Карточка итога (03-result.png): статус, крупная фраза, детали. */
function Outcome({ eyebrow, phrase, confirmed, children }: { eyebrow: string; phrase: string; confirmed: boolean; children: ReactNode }) {
  return (
    <section className="space-y-7 rounded-3xl border border-line bg-white p-6 sm:p-10">
      <div className="flex items-center gap-2.5"><Dot tone={confirmed ? 'success' : 'neutral'} /><span className="text-sm text-muted">{eyebrow}</span></div>
      <h1 className="text-4xl font-semibold leading-[1.05] tracking-[-0.035em] text-balance sm:text-5xl">{phrase}</h1>
      {children}
    </section>
  )
}

export default function ResultView({ state }: { state: AttemptState }) {
  const r = state.result
  if (!r) return null
  const confirmed = r.decision === 'confirmed'
  if (state.skill_code === 'ai' && r.ai) {
    const m = r.ai
    const need = state.ai
    return (
      <Page narrow>
        <Outcome eyebrow="Итог «Работы с ИИ»" phrase={r.phrase} confirmed={confirmed}>
          <ul className="space-y-2 text-[15px]">
            <li>Точность: {pct(m.accuracy)}{need && ` (нужно от ${pct(need.pass_accuracy)})`}</li>
            <li>Принятые ошибки ИИ с учётом уверенности: {pct(m.miss_weighted)}{need && ` (допустимо до ${pct(need.pass_miss)})`}</li>
            <li>Отклонённые верные решения: {pct(m.false_reject)}</li>
            <li>{m.in_time ? `Время: ${m.minutes} мин` : 'Время вышло до последнего ответа'}</li>
          </ul>
          {confirmed
            ? <Notice tone="success">Навык отмечен в профиле. ИИ-инструменты из вашего стека отмечены галочкой.</Notice>
            : <p className="text-sm text-muted">Неудачную попытку работодатели не видят. Пересдать можно через {days(need?.cooldown_days ?? 14)}.</p>}
        </Outcome>
        <LinkButton to="/candidate/skills" variant="secondary">К навыкам</LinkButton>
      </Page>
    )
  }
  if (state.target_grade === 'skill') {
    return (
      <Page narrow>
        <Outcome eyebrow="Итог теста навыка" phrase={r.phrase} confirmed={confirmed}>
          {confirmed
            ? <Notice tone="success">Технологии навыка теперь отмечены ✓ в профиле и в подборке.</Notice>
            : <p className="text-sm text-muted">Неудачную попытку работодатели не видят. Пересдать можно через 14 дней.</p>}
        </Outcome>
        <LinkButton to="/candidate/skills" variant="secondary">К навыкам</LinkButton>
      </Page>
    )
  }
  const next = NEXT[state.target_grade]
  // Надёжность самого вывода: для «не подтверждён» — вероятность, что грейда действительно нет
  const reliability = r.reliability === null ? null : confirmed ? r.reliability : 1 - r.reliability
  return (
    <Page narrow>
      <Outcome eyebrow="Итог теста" phrase={r.phrase} confirmed={confirmed}>
        {reliability !== null && (
          <div className="space-y-2.5">
            <div className="flex justify-between text-sm"><span className="text-muted">Надёжность вывода</span><span className="font-mono font-semibold">{pct(reliability)}</span></div>
            <Meter value={reliability} label="Надёжность вывода" tone={confirmed ? 'success' : 'primary'} />
          </div>
        )}
        <details className="text-sm">
          <summary className={`cursor-pointer ${linkClass}`}>Почему такой вывод</summary>
          <p className="mt-2 text-[13px] leading-relaxed text-muted">Задания подбирались по вашим ответам. Тест остановился, когда результат стал достаточно надёжным.</p>
          <ObjectionForm attemptId={state.id} />
        </details>
        <StatGrid>
          <Stat label="Грейд" value={GRADE_TITLE[state.target_grade]} />
          <Stat label="Формат" value={r.express ? 'Экспресс' : 'Полный тест'} />
          <Stat label="Заданий" value={state.n_answered} />
        </StatGrid>
        {r.express && <p className="text-sm">После полного теста позиция в категории станет точнее.</p>}
        {r.border && <Notice tone="warning">Результат на границе грейда. Когда откроется пересдача, лучше пройти полный тест ещё раз.</Notice>}
      </Outcome>
      {r.confident && next ? (
        <section className="flex flex-wrap items-center justify-between gap-5 rounded-3xl bg-primary px-6 py-7 text-white sm:px-8">
          <div>
            <p className="text-sm text-primary-soft">Уверенный результат открыл</p>
            <p className="mt-1 text-2xl font-semibold tracking-[-0.02em]">Тест на {GRADE_TITLE[next]}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <LinkButton to={`/test/rules?grade=${next}`} variant="light">Пройти сейчас</LinkButton>
            <LinkButton to="/" variant="outline-light">В кабинет</LinkButton>
          </div>
        </section>
      ) : <LinkButton to="/" variant="secondary">В кабинет</LinkButton>}
    </Page>
  )
}
