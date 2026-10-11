import { useQuery } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { GRADE_TITLE } from '../../api/assessment'
import { STATUS_TITLE } from '../../api/contacts'
import { candidatePdfUrl, FORMAT_TITLE, getSummary, SKILL_TITLE, type Card } from '../../api/employer'
import { Button, Pill, TechChip } from '../ui'
import { linkClass } from '../ui-classes'

const CONFLICT: Record<string, string> = { must: 'не хватает двух и более обязательных технологий', format: 'формат работы несовместим', salary: 'вилка сильно ниже ожиданий' }

/** Короткая сводка: шаблон или перефразирование ИИ с проверкой фактов. Запрашивается только при раскрытии карточки. */
function CardSummary({ needId, cardRef }: { needId: string; cardRef: string }) {
  const q = useQuery({ queryKey: ['summary', needId, cardRef], queryFn: () => getSummary(needId, cardRef), staleTime: Infinity })
  if (!q.data) return null
  return <p className="mb-2 italic">{q.data.text}</p>
}

/** Карточка кандидата в подборке и ячейке карты (07-selection.png). */
export function CandidateCard({ card, onPin, actions, needId }: { card: Card; onPin?: (ref: string, pin: boolean) => void; actions?: ReactNode; needId?: string }) {
  const [open, setOpen] = useState(false)
  const confirmed = card.grade_status === 'confirmed'
  const meta = [card.experience_years != null ? `опыт ${card.experience_years} г.` : null, card.formats.map((f) => FORMAT_TITLE[f]).join(', ') || null, card.city].filter(Boolean).join(' · ')
  const warnings = [...card.conflicts.map((c) => CONFLICT[c] ?? c), ...(card.filter_mismatch ? [card.filter_mismatch] : [])]
  return (
    <article className="space-y-3.5 rounded-[18px] border border-line bg-white p-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-[15px] font-semibold">{card.alias}</span>
          <Pill tone={confirmed ? 'success' : 'neutral'}>{GRADE_TITLE[card.grade]} · {confirmed ? 'подтверждён тестом' : 'не подтверждён'}</Pill>
          {card.express && <Pill>экспресс</Pill>}
          {card.interview_badge && <Pill tone="primary">{card.interview_badge}</Pill>}
          {card.minor && <Pill tone="warning">14–17 лет: стажировка или каникулярная работа</Pill>}
          {card.signal && <Pill tone="solid">Хочет к вам</Pill>}
          {card.contact_status && <Pill tone="primary">приглашение: {STATUS_TITLE[card.contact_status]}</Pill>}
          {card.readiness && <span title={card.readiness.tooltip} className="cursor-help rounded-full border border-line-strong px-2.5 py-0.5 text-xs">Готовность: {card.readiness.level}</span>}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {onPin && <Button variant="secondary" size="sm" className={card.pinned ? 'bg-canvas' : ''} onClick={() => onPin(card.ref, !card.pinned)}>{card.pinned ? 'Убрать из шортлиста' : 'В шортлист'}</Button>}
          {actions}
        </div>
      </header>
      {card.explanation.lines.length > 0 && (
        <ul className="space-y-1.5">{card.explanation.lines.map((l) => (
          <li key={l} className="flex gap-2.5 text-sm leading-snug"><span aria-hidden="true" className="text-subtle">—</span>{l}</li>
        ))}</ul>
      )}
      {card.stack.length > 0 && <div className="flex flex-wrap gap-1.5">{card.stack.slice(0, 10).map((s) => <TechChip key={s.tech} tech={s.tech} confirmed={s.state === 'confirmed'} />)}</div>}
      {card.skills.length > 0 && <p className="text-[13px] text-muted">Навыки: {card.skills.map((s) => SKILL_TITLE[s] ?? s).join(', ')}</p>}
      {(meta || warnings.length > 0) && (
        <div className="flex flex-wrap justify-between gap-3 border-t border-line-soft pt-3 text-[13px] text-muted">
          <span>{meta}</span>
          {warnings.length > 0 && <span className="text-danger">{warnings.join('; ')}</span>}
        </div>
      )}
      {(needId || card.explanation.missing.length > 0 || card.explanation.counterfactual) && (
        <button type="button" aria-expanded={open} className={`text-sm ${linkClass}`} onClick={() => setOpen((v) => !v)}>{open ? 'Скрыть' : 'Подробнее'}</button>
      )}
      {open && (
        <div className="space-y-1 rounded-xl bg-surface-2 p-4 text-sm">
          {needId && <CardSummary needId={needId} cardRef={card.ref} />}
          {card.explanation.missing.length > 0 && <><p className="font-semibold">Чего не хватает</p><ul className="list-disc pl-5">{card.explanation.missing.map((m) => <li key={m}>{m}</li>)}</ul></>}
          {card.explanation.counterfactual && <p>{card.explanation.counterfactual}</p>}
          {needId && <a className={`inline-block pt-1 ${linkClass}`} href={candidatePdfUrl(needId, card.ref)}>PDF-профиль</a>}
        </div>
      )}
    </article>
  )
}
