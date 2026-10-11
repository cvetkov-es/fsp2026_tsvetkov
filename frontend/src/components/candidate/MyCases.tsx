import { useQuery } from '@tanstack/react-query'
import { getMyCases } from '../../api/complaints'
import LoadError from '../LoadError'
import { Card } from '../ui'

const day = (iso: string) => new Date(iso).toLocaleDateString('ru-RU')

/** «Мои обращения»: споры, жалобы и возражения с итогом и текстом модератора. */
export default function MyCases() {
  const q = useQuery({ queryKey: ['my-cases'], queryFn: getMyCases })
  return (
    <Card>
      <h2 className="text-lg font-semibold">Мои обращения</h2>
      {q.isError && <LoadError error={q.error} />}
      {q.data?.length === 0 && <p className="mt-2 text-sm text-muted">Обращений пока нет.</p>}
      <ul className="mt-2 space-y-3">
        {q.data?.map((c) => (
          <li key={c.id} className="text-sm">
            <p className="font-semibold">{c.type_title} <span className="font-normal text-muted">· {day(c.created_at)}</span></p>
            <p>{c.status === 'open'
              ? `на рассмотрении${c.due_at ? ` · ответ до ${day(c.due_at)}` : ''}`
              : `рассмотрено${c.outcome ? ` · ${c.outcome}` : ''}`}</p>
            {c.resolution_text && <p className="text-muted">{`Комментарий модератора: ${c.resolution_text}`}</p>}
          </li>
        ))}
      </ul>
    </Card>
  )
}
