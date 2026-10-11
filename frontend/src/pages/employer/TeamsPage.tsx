import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { GRADE_TITLE, type Grade } from '../../api/assessment'
import { Link } from 'react-router-dom'
import { getTeams } from '../../api/fsp'
import { getGroups } from '../../api/groups'
import { TeamInviteForm } from '../../components/employer/TeamInviteForm'
import LoadError from '../../components/LoadError'
import { Button, Card } from '../../components/ui'

const SPECS: [string, string][] = [['', 'Все'], ['backend', 'Backend'], ['frontend', 'Frontend'], ['data', 'Data / Analytics']]

/** Найм команды целиком (процесс 4.5): призовые команды ФСП, где на платформе не меньше двух участников. */
export default function TeamsPage() {
  const [spec, setSpec] = useState('')
  const q = useQuery({ queryKey: ['teams', spec], queryFn: () => getTeams(spec || undefined) })
  const groups = useQuery({ queryKey: ['groups'], queryFn: getGroups })
  const [inviting, setInviting] = useState<string | null>(null)
  return (
    <div className="space-y-4 p-6">
      <h1 className="text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">Команды ФСП</h1>
      <p className="text-sm text-muted">Команды-призёры стартов ФСП, в которых на платформе есть хотя бы двое. Сыгранность: сколько стартов участники в среднем прошли вместе. Личный вклад каждого мы не оцениваем.</p>
      <div className="flex flex-wrap gap-2">{SPECS.map(([code, title]) => (
        <button key={code} onClick={() => setSpec(code)} className={`rounded-full px-3 py-1 text-sm ${spec === code ? 'bg-ink text-white' : 'bg-line-soft text-ink-2'}`}>{title}</button>
      ))}</div>
      {groups.isError && <LoadError error={groups.error} />}
      {groups.data && groups.data.length > 0 && (
        <Card>
          <h2 className="mb-2 font-semibold">Отправленные командные приглашения</h2>
          <ul className="space-y-1 text-sm">{groups.data.map((g) => (
            <li key={g.id}><Link className="text-primary hover:underline" to={`/employer/groups/${g.id}`}>{`«${g.team_name}» · ${g.need_title}`}</Link>
              <span className="ml-2 text-muted">{`участников: ${g.size} · до ${new Date(g.deadline).toLocaleDateString('ru-RU')}`}</span></li>
          ))}</ul>
        </Card>
      )}
      {q.data?.length === 0 && <Card><p>Подходящих команд пока нет.</p></Card>}
      {q.data?.map((t) => (
        <Card key={t.team_id}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold">«{t.team_name ?? t.team_id}»</h2>
            <span className="text-sm">{t.place} место{t.field_size ? ` из ${t.field_size}` : ''} · {t.competition_title}</span>
          </div>
          <p className="text-sm text-muted">{t.discipline_title} · на платформе {t.on_platform} из {t.team_size} · сыгранность {t.cohesion.toFixed(1)}</p>
          <ul className="mt-2 flex flex-wrap gap-2 text-sm">{t.members.map((m) => (
            <li key={m.ref} className="rounded-full bg-line-soft px-3 py-1 font-mono">{m.alias} · {m.grade ? GRADE_TITLE[m.grade as Grade] : '—'}{m.grade_status === 'confirmed' ? ' ✓' : ''}</li>
          ))}</ul>
          <p className="mt-2 text-xs text-muted">Пригласите всю команду сразу, у каждого будет своя вилка. По одному можно пригласить из подборки.</p>
          {inviting === t.team_id ? <TeamInviteForm team={t} /> : <Button type="button" className="mt-2" onClick={() => setInviting(t.team_id)}>Пригласить команду</Button>}
        </Card>
      ))}
    </div>
  )
}
