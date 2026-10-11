import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { GRADE_TITLE, type Grade } from '../../api/assessment'
import { ApiError } from '../../api/client'
import { errorText } from '../../api/errors'
import {
  getBoard, getInterviewHelper, LEVEL_TITLE, moveStage, REJECT_REASONS, STAGE_TITLE, VOTE_NOTE, VOTE_STATE_TITLE,
  type BoardCard, type InterviewHelper, type Level, type Stage,
} from '../../api/hiring'
import { Button, Card } from '../../components/ui'

const COLUMNS: (Stage | null)[] = [null, 'first', 'technical', 'offer', 'hired', 'rejected']
// Этапы идут только вперёд; на «техническом» и в финале можно переответить (последний ответ перезаписывает прежний)
const NEXT: Record<Stage | 'none', Stage[]> = {
  none: ['first', 'technical', 'offer', 'hired', 'rejected'], first: ['technical', 'offer', 'hired', 'rejected'],
  technical: ['technical', 'offer', 'hired', 'rejected'], offer: ['hired', 'rejected'], hired: ['hired'], rejected: ['rejected'],
}
const ASK: Stage[] = ['technical', 'hired', 'rejected']
const LEVELS: Level[] = ['below', 'meets', 'above', 'unknown']
const day = (iso: string) => new Date(iso).toLocaleDateString('ru-RU')
const gradeTitle = (g: string) => GRADE_TITLE[g as Grade] ?? g
const daysText = (n: number) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? 'день' : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? 'дня' : 'дней'}`
const ACCEPTED = 'Приглашение принято'

function StageForm({ card, onDone }: { card: BoardCard; onDone: () => void }) {
  const options = NEXT[card.stage ?? 'none']
  const [stage, setStage] = useState<Stage>(options[0])
  const [level, setLevel] = useState<Level | null>(null)
  const [reason, setReason] = useState('')
  const [areas, setAreas] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const ask = ASK.includes(stage)
  const final = stage === 'hired' || stage === 'rejected'
  const ready = (!ask || level !== null) && (stage !== 'rejected' || reason !== '')
  const save = async () => {
    setError(null)
    setBusy(true)
    try {
      await moveStage(card.contact_id, { stage, level: ask ? level ?? undefined : undefined, reason: stage === 'rejected' ? reason : undefined, weak_areas: final ? areas : [] })
      onDone()
    } catch (e) { setError(e instanceof ApiError ? e.title : 'Не удалось сохранить этап') } finally { setBusy(false) }
  }
  return (
    <div className="mt-2 space-y-2 rounded-lg bg-surface-2 p-2 text-sm">
      <label className="flex items-center gap-2">Этап
        <select aria-label="Этап" className="rounded border border-line-strong px-1 py-0.5" value={stage} onChange={(e) => { setStage(e.target.value as Stage); setLevel(null) }}>
          {options.map((s) => <option key={s} value={s}>{STAGE_TITLE[s]}</option>)}
        </select>
      </label>
      {ask && (
        <fieldset>
          <legend className="font-semibold">Уровень относительно ваших ожиданий{card.grade ? ` от грейда ${gradeTitle(card.grade)}` : ''}</legend>
          {LEVELS.map((l) => (
            <label key={l} className="mr-3 inline-flex items-center gap-1"><input type="radio" name={`level-${card.contact_id}`} checked={level === l} onChange={() => setLevel(l)} />{LEVEL_TITLE[l]}</label>
          ))}
        </fieldset>
      )}
      {stage === 'rejected' && (
        <select aria-label="Причина отказа" className="rounded border border-line-strong px-1 py-0.5" value={reason} onChange={(e) => setReason(e.target.value)}>
          <option value="" disabled>Причина отказа</option>
          {Object.entries(REJECT_REASONS).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
        </select>
      )}
      {final && card.area_options.length > 0 && (
        <fieldset>
          <legend>Слабые области (по желанию)</legend>
          {card.area_options.map((a) => (
            <label key={a.code} className="mr-3 inline-flex items-center gap-1">
              <input type="checkbox" checked={areas.includes(a.code)} onChange={(e) => setAreas(e.target.checked ? [...areas, a.code] : areas.filter((x) => x !== a.code))} />{a.title}
            </label>
          ))}
        </fieldset>
      )}
      <Button disabled={!ready || busy} onClick={() => void save()}>Сохранить</Button>
      {error && <p role="alert" className="text-danger">{error}</p>}
    </div>
  )
}

/** Помощник к собеседованию (процесс 4.7): вопросы с темой и причиной выбора; повтор по контакту лимит не тратит. */
function Helper({ contactId }: { contactId: string }) {
  const [data, setData] = useState<InterviewHelper | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  return (
    <div className="mt-1">
      <button className="text-primary hover:underline" disabled={busy} onClick={async () => {
        setError(null)
        setBusy(true)
        try { setData(await getInterviewHelper(contactId)) } catch (e) { setError(errorText(e)) } finally { setBusy(false) }
      }}>Вопросы к собеседованию</button>
      {error && <p role="alert" className="text-xs text-danger">{error}</p>}
      {data && (
        <div className="mt-1 rounded-lg bg-surface-2 p-2 text-xs">
          <ol className="list-decimal space-y-1 pl-4">{data.questions.map((q) => (
            <li key={q.text}><p>{q.text}</p><p className="text-muted">{`${q.topic} · ${q.reason}`}</p></li>
          ))}</ol>
          <p className="mt-1 text-muted">{`Использовано ${data.used} из ${data.limit} за ${data.window_days} дней`}</p>
        </div>
      )}
    </div>
  )
}

function BoardCardView({ card, onDone, trust }: { card: BoardCard; onDone: () => void; trust: string }) {
  const [open, setOpen] = useState(false)
  return (
    <li className="rounded-xl border border-line bg-white p-2 text-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono font-semibold">{card.alias}</span>
        {card.stage_at && <span className="text-xs text-subtle">{day(card.stage_at)}</span>}
      </div>
      {card.level && <p>Уровень: {LEVEL_TITLE[card.level]}</p>}
      {card.revoked && <p className="text-xs text-danger">Кандидат скрыл контакты. Карточка доступна только для просмотра.</p>}
      {card.vote && <p className="text-xs text-muted">Оценка: {VOTE_STATE_TITLE[card.vote.state]}{card.vote.state === 'pending' ? ` ${day(card.vote.effective_at)}` : ''}</p>}
      {card.vote_note && VOTE_NOTE[card.vote_note] && <p className="text-xs text-muted">Оценка {VOTE_NOTE[card.vote_note]}</p>}
      {card.reason && <p className="text-xs">Причина: {REJECT_REASONS[card.reason] ?? card.reason}</p>}
      <div className="mt-1 flex gap-3">
        {card.chat_open && <Link className="text-primary hover:underline" to={`/contacts/${card.contact_id}`}>Чат</Link>}
        {card.chat_open && NEXT[card.stage ?? 'none'].length > 0 && (
          <button className="text-primary hover:underline" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? 'Скрыть' : 'Изменить этап'}</button>
        )}
      </div>
      {card.chat_open && (trust === 'L2' || trust === 'L3') && <Helper contactId={card.contact_id} />}
      {open && <StageForm card={card} onDone={() => { setOpen(false); onDone() }} />}
    </li>
  )
}

/** Доска найма (процесс 4.7): этапы по принятым приглашениям и вопрос об уровне — из него складываются голоса (процесс 5). */
export default function BoardPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['board', id], queryFn: () => getBoard(id) })
  const b = q.data
  const reload = () => void qc.invalidateQueries({ queryKey: ['board', id] })
  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">Доска найма{b ? ` · ${b.title}` : ''}</h1>
        <Link className="text-sm text-primary hover:underline" to={`/employer/needs/${id}/invitations`}>← к приглашениям</Link>
      </div>
      {b && (
        <p className="text-sm text-muted">{b.vote_weight === null
          ? 'С уровнем доверия L0 оценки сохраняются, но не засчитываются.'
          : `Оценка «ниже», «соответствует» или «выше» вступит в силу через ${daysText(b.dispute_days)}, если кандидат её не оспорит. Оценок за 30 дней: ${b.votes_used} из ${b.votes_limit}, вес оценки ${b.vote_weight}.`}</p>
      )}
      {q.isPending && <p>Загрузка…</p>}
      {q.isError && <p role="alert" className="text-danger">{q.error instanceof ApiError ? q.error.title : 'Не удалось загрузить доску'}</p>}
      {b?.cards.length === 0 && <Card><p>Здесь появятся кандидаты, принявшие приглашения по этой потребности.</p></Card>}
      {b && b.cards.length > 0 && (
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          {COLUMNS.map((col) => (
            <section key={col ?? 'none'} aria-label={col ? STAGE_TITLE[col] : ACCEPTED} className="rounded-2xl bg-surface-2 p-2">
              <h2 className="mb-2 text-sm font-semibold">{col ? STAGE_TITLE[col] : ACCEPTED}</h2>
              <ul className="space-y-2">{b.cards.filter((c) => c.stage === col).map((c) => <BoardCardView key={c.contact_id} card={c} onDone={reload} trust={b.trust_level} />)}</ul>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
