import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { errorText } from '../../api/errors'
import { finalizeGroup, getGroup, MEMBER_STATUS, withdrawGroup, type Group } from '../../api/groups'
import LoadError from '../../components/LoadError'
import { Button, Card } from '../../components/ui'

const shortDay = (iso: string) => new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })

function stateText(g: Group): string {
  switch (g.state) {
    case 'open': return `открыто до ${shortDay(g.deadline)} · минимум ${g.min_reached_now ? 'набран' : 'не набран'}`
    case 'min_reached': return 'минимум набран'
    case 'not_reached': return 'минимум не набран'
    case 'closed': return 'закрыто'
    default: return 'срок вышел'
  }
}

/** Страница командного приглашения (процесс 4.5): статусы участников, офферы v2 после срока, отзыв группы. */
export default function GroupPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['group', id], queryFn: () => getGroup(id) })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const g = q.data
  const act = async (f: (id: string) => Promise<unknown>) => {
    setError(null)
    setBusy(true)
    try { await f(id); await qc.invalidateQueries({ queryKey: ['group', id] }) } catch (e) { setError(errorText(e)) } finally { setBusy(false) }
  }
  return (
    <div className="space-y-4 p-6">
      {q.isError && <LoadError error={q.error} />}
      {q.isLoading && <p className="text-sm text-muted">Загрузка…</p>}
      {g && (
        <Card>
          <h1 className="text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">{`Команда «${g.team_name}» · потребность «${g.need_title}»`}</h1>
          <p className="mt-1 font-semibold">{stateText(g)}</p>
          <p className="text-sm text-muted">{`Приглашено ${g.size}, минимальный состав ${g.min_size}, ответить до ${new Date(g.deadline).toLocaleDateString('ru-RU')}. Участники не видят ответов друг друга.`}</p>
          <ul className="mt-3 space-y-2">{g.members.map((m) => (
            <li key={m.contact_id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line p-2 text-sm">
              <span className="font-mono font-bold">{m.alias}</span>
              <span>{`${m.salary_from.toLocaleString('ru-RU')} – ${m.salary_to.toLocaleString('ru-RU')} ₽${m.hours_per_week ? ` · ${m.hours_per_week} ч в неделю` : ''}`}</span>
              <span className="rounded-full bg-line-soft px-2 py-0.5 text-xs text-ink">{MEMBER_STATUS[m.status] ?? m.status}</span>
            </li>
          ))}</ul>
          <div className="mt-4 flex flex-wrap items-center gap-4">
            {g.state === 'min_reached' && <Button disabled={busy} onClick={() => void act(finalizeGroup)}>Отправить личные приглашения согласившимся</Button>}
            {g.state !== 'closed' && <button className="text-sm text-danger hover:underline" disabled={busy} onClick={() => void act(withdrawGroup)}>Отозвать приглашение команды</button>}
            <Link className="text-sm text-primary hover:underline" to="/employer/teams">← к командам</Link>
          </div>
          {error && <p role="alert" className="mt-2 text-sm text-danger">{error}</p>}
        </Card>
      )}
    </div>
  )
}
