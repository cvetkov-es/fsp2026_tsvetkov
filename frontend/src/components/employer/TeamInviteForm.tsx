import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { errorText } from '../../api/errors'
import { listNeeds } from '../../api/employer'
import type { FspTeam } from '../../api/fsp'
import { createGroup, getGroupLimits } from '../../api/groups'
import { Button, Field, Input } from '../ui'

type Edit = { from?: string; to?: string; hours?: string }
const ymd = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

/** Срок — конец выбранного дня, поэтому последний допустимый день на один меньше предела в днях. */
function deadlineRange(ttlDays: number): [string, string] {
  const now = Date.now()
  return [ymd(new Date(now)), ymd(new Date(now + (ttlDays - 1) * 86_400_000))]
}

/** Командное приглашение (процесс 4.5): у каждого участника своя вилка, квота потребности тратится на каждого. */
export function TeamInviteForm({ team }: { team: FspTeam }) {
  const nav = useNavigate()
  const needs = useQuery({ queryKey: ['needs'], queryFn: listNeeds })
  const limits = useQuery({ queryKey: ['group-limits'], queryFn: getGroupLimits })
  const active = needs.data?.filter((n) => n.status === 'active') ?? []
  const [needId, setNeedId] = useState('')
  const need = active.find((n) => n.id === needId) ?? active[0]
  const [edits, setEdits] = useState<Record<string, Edit>>({})
  const [skipped, setSkipped] = useState<string[]>([])  // участники, которых не приглашаем
  const [minSize, setMinSize] = useState('2')
  const [date, setDate] = useState('')
  const [description, setDescription] = useState('')
  const [why, setWhy] = useState('')
  const [next, setNext] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (!need) return <p className="mt-3 text-sm">Сначала создайте потребность.</p>
  const edit = (ref: string, k: keyof Edit, v: string) => setEdits((e) => ({ ...e, [ref]: { ...e[ref], [k]: v.replace(/\D/g, '') } }))
  const from = (ref: string) => edits[ref]?.from ?? String(need.salary_from)
  const to = (ref: string) => edits[ref]?.to ?? String(need.salary_to)
  const min = Number(minSize)
  const chosen = team.members.filter((m) => !skipped.includes(m.ref))
  const n = chosen.length
  const forksOk = chosen.every((m) => Number(from(m.ref)) > 0 && Number(from(m.ref)) <= Number(to(m.ref)) && (!m.minor || Number(edits[m.ref]?.hours) > 0))
  const ready = forksOk && n >= (limits.data?.min_team ?? 2) && min >= (limits.data?.min_team ?? 2) && min <= n && !!date && !!why.trim() && !!next.trim()
  const [first, last] = deadlineRange(limits.data?.ttl_days ?? 1)
  const send = async () => {
    setError(null)
    setBusy(true)
    try {
      const g = await createGroup({
        need_id: need.id, team_id: team.team_id, min_size: min, deadline: new Date(`${date}T23:59:59`).toISOString(),
        members: chosen.map((m) => ({
          ref: m.ref, salary_from: Number(from(m.ref)), salary_to: Number(to(m.ref)),
          ...(m.minor ? { hours_per_week: Number(edits[m.ref]?.hours) } : {}),
        })),
        gross_net: need.gross_net, description, why_you: why.trim(), next_step: next.trim(), contact_method: need.contact_method,
      })
      nav(`/employer/groups/${g.id}`)
    } catch (e) { setError(errorText(e)) } finally { setBusy(false) }
  }
  return (
    <div className="mt-3 space-y-3 rounded-xl border border-line-strong p-4 text-sm">
      <p className="text-muted">Каждый участник занимает место в квоте потребности. Участники соглашаются условно. Контакты участника вы получите после срока, когда отправите ему личное приглашение и он его примет.</p>
      <Field label="Потребность" htmlFor={`gneed-${team.team_id}`}>
        <select id={`gneed-${team.team_id}`} aria-label="Потребность" className="w-full rounded-lg border border-line-strong px-3 py-2" value={need.id} onChange={(e) => setNeedId(e.target.value)}>
          {active.map((x) => <option key={x.id} value={x.id}>{x.title}</option>)}
        </select>
      </Field>
      <ul className="space-y-2">{team.members.map((m) => (
        <li key={m.ref} className={`flex flex-wrap items-end gap-2 ${skipped.includes(m.ref) ? 'opacity-50' : ''}`}>
          <label className="flex w-40 items-center gap-2 font-mono font-bold">
            <input type="checkbox" aria-label={`Приглашать ${m.alias}`} checked={!skipped.includes(m.ref)}
              onChange={(e) => setSkipped((s) => e.target.checked ? s.filter((x) => x !== m.ref) : [...s, m.ref])} />{m.alias}</label>
          <label className="text-xs">Вилка от, ₽
            <Input aria-label={`${m.alias}: вилка от, ₽`} inputMode="numeric" value={from(m.ref)} onChange={(e) => edit(m.ref, 'from', e.target.value)} /></label>
          <label className="text-xs">Вилка до, ₽
            <Input aria-label={`${m.alias}: вилка до, ₽`} inputMode="numeric" value={to(m.ref)} onChange={(e) => edit(m.ref, 'to', e.target.value)} /></label>
          {m.minor && (
            <label className="text-xs">Часов в неделю
              <Input aria-label={`${m.alias}: часов в неделю`} inputMode="numeric" value={edits[m.ref]?.hours ?? ''} onChange={(e) => edit(m.ref, 'hours', e.target.value)} /></label>
          )}
        </li>
      ))}</ul>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Минимальный состав" htmlFor={`gmin-${team.team_id}`}>
          <Input id={`gmin-${team.team_id}`} aria-label="Минимальный состав" inputMode="numeric" value={minSize} onChange={(e) => setMinSize(e.target.value.replace(/\D/g, ''))} /></Field>
        <Field label="Ответить до" htmlFor={`gdate-${team.team_id}`}>
          <input id={`gdate-${team.team_id}`} aria-label="Ответить до" type="date" className="w-full rounded-lg border border-line-strong px-3 py-2"
            min={first} max={limits.data ? last : undefined} value={date} onChange={(e) => setDate(e.target.value)} /></Field>
      </div>
      <Field label="Описание (необязательно)" htmlFor={`gdesc-${team.team_id}`}>
        <textarea id={`gdesc-${team.team_id}`} aria-label="Описание" rows={2} maxLength={2000} className="w-full rounded-lg border border-line-strong p-2" value={description} onChange={(e) => setDescription(e.target.value)} /></Field>
      <Field label="Почему вы" htmlFor={`gwhy-${team.team_id}`}>
        <textarea id={`gwhy-${team.team_id}`} aria-label="Почему вы" rows={2} maxLength={1000} className="w-full rounded-lg border border-line-strong p-2" value={why} onChange={(e) => setWhy(e.target.value)} /></Field>
      <Field label="Следующий шаг" htmlFor={`gnext-${team.team_id}`}>
        <Input id={`gnext-${team.team_id}`} aria-label="Следующий шаг" maxLength={500} value={next} onChange={(e) => setNext(e.target.value)} /></Field>
      {error && <p role="alert" className="text-danger">{error}</p>}
      <Button type="button" disabled={!ready || busy} onClick={() => void send()}>Отправить командное приглашение</Button>
    </div>
  )
}
