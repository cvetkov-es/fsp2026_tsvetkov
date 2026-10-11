import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError } from '../../api/client'
import { errorText } from '../../api/errors'
import { getInviteDraft, sendInvitation, type InviteDraft, type InviteInput } from '../../api/contacts'
import { Button, Field, Input } from '../ui'

/** Как отправить оффер; по умолчанию — обычное приглашение по потребности, «Пригласить автора» подставляет своё. */
type Send = (v: InviteInput) => Promise<unknown>

/** Оффер с предзаполнением (процесс 2.8): вилка, gross/net и связь — из потребности, «почему вы» — из объяснения. */
export function InviteForm({ needId, cardRef, onSent, send }: { needId: string; cardRef: string; onSent: () => void; send?: Send }) {
  const draft = useQuery({ queryKey: ['invite-draft', needId, cardRef], queryFn: () => getInviteDraft(needId, cardRef) })
  if (draft.isError) return <p role="alert" className="mt-2 text-sm text-danger">{errorText(draft.error, 'Не удалось подготовить черновик')}</p>
  if (!draft.data) return <p className="text-sm">Готовим черновик приглашения…</p>
  return <InviteFormView draft={draft.data} needId={needId} onSent={onSent} send={send} />
}

function InviteFormView({ draft, needId, onSent, send }: { draft: InviteDraft; needId: string; onSent: () => void; send?: Send }) {
  const [v, setV] = useState<InviteInput>({ ref: draft.ref, salary_from: draft.salary_from, salary_to: draft.salary_to, gross_net: draft.gross_net,
    description: draft.description, why_you: draft.why_you, next_step: draft.next_step, contact_method: draft.contact_method })
  const [hours, setHours] = useState('')
  const [error, setError] = useState<string | null>(null)
  const cap = draft.minor_hours_limit ?? null
  const hoursNum = Number(hours)
  const hoursOk = cap === null || (hoursNum > 0 && hoursNum <= cap)
  const set = <K extends keyof InviteInput>(k: K, x: InviteInput[K]) => setV({ ...v, [k]: x })
  const num = (s: string) => Number(s.replace(/\D/g, ''))
  const left = draft.quota_limit - draft.quota_used
  return (
    <form className="mt-3 space-y-3 rounded-xl border border-line-strong p-4" onSubmit={async (e) => {
      e.preventDefault(); setError(null)
      try { const body = cap === null ? v : { ...v, hours_per_week: hoursNum }; await (send ? send(body) : sendInvitation(needId, body)); onSent() } catch (err) { setError(err instanceof ApiError ? `${err.title}${err.detail ? `: ${err.detail}` : ''}` : 'Не удалось отправить приглашение') }
    }}>
      <p className="text-sm text-muted">Приглашение для {draft.alias} · свободно в квоте: {left} из {draft.quota_limit}</p>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Вилка от, ₽" htmlFor="inv-from"><Input id="inv-from" inputMode="numeric" value={v.salary_from} onChange={(e) => set('salary_from', num(e.target.value))} /></Field>
        <Field label="Вилка до, ₽" htmlFor="inv-to"><Input id="inv-to" inputMode="numeric" value={v.salary_to} onChange={(e) => set('salary_to', num(e.target.value))} /></Field>
        <fieldset className="flex items-end gap-3 pb-2 text-sm">
          <label className="flex gap-1"><input type="radio" checked={v.gross_net === 'gross'} onChange={() => set('gross_net', 'gross')} />до вычета</label>
          <label className="flex gap-1"><input type="radio" checked={v.gross_net === 'net'} onChange={() => set('gross_net', 'net')} />на руки</label>
        </fieldset>
      </div>
      <Field label="Почему вы" htmlFor="inv-why"><textarea id="inv-why" rows={3} className="w-full rounded-lg border border-line-strong p-2 text-sm" value={v.why_you} onChange={(e) => set('why_you', e.target.value)} /></Field>
      <Field label="Описание" htmlFor="inv-desc"><textarea id="inv-desc" rows={2} className="w-full rounded-lg border border-line-strong p-2 text-sm" value={v.description} onChange={(e) => set('description', e.target.value)} /></Field>
      {cap !== null && (
        <Field label={`Часов в неделю (до ${cap})`} htmlFor="inv-hours">
          <Input id="inv-hours" aria-label={`Часов в неделю (до ${cap})`} inputMode="numeric" value={hours} onChange={(e) => setHours(e.target.value.replace(/\D/g, ''))} />
          <p className="mt-1 text-xs text-muted">Кандидату нет 18 лет. Предел часов задаёт ст. 92 ТК РФ.</p>
        </Field>
      )}
      <Field label="Следующий шаг" htmlFor="inv-next"><Input id="inv-next" value={v.next_step} onChange={(e) => set('next_step', e.target.value)} /></Field>
      {error && <p className="text-sm text-danger">{error}</p>}
      <Button type="submit" disabled={left <= 0 || !v.why_you.trim() || !v.next_step.trim() || v.salary_from > v.salary_to || !hoursOk}>Отправить приглашение</Button>
    </form>
  )
}
