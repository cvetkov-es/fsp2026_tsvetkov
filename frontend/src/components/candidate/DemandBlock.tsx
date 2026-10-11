import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getDemand, type Demand } from '../../api/initiative'
import { Card } from '../ui'

const STATE: Record<Demand['top'][number]['state'], string> = { confirmed: 'подтверждено', declared: 'заявлено', missing: 'не подтверждено' }

function companies(n: number): string {
  const m10 = n % 10
  const m100 = n % 100
  if (m10 === 1 && m100 !== 11) return 'компания'
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return 'компании'
  return 'компаний'
}

/** Спрос как обратная связь (процесс 2.9): без чисел, пока компаний меньше порога; порог приходит с сервера. */
export default function DemandBlock() {
  const q = useQuery({ queryKey: ['demand'], queryFn: getDemand, retry: false })
  const d = q.data
  if (!d || !d.category) return null
  if (!d.enough) {
    return (
      <Card>
        <p className="text-sm text-muted">Спрос в вашей категории</p>
        <p className="text-sm">{`Покажем спрос, когда «${d.category}» будут искать хотя бы ${d.min_companies} ${companies(d.min_companies)}.`}</p>
      </Card>
    )
  }
  return (
    <Card>
      <p className="text-sm text-muted">Спрос в вашей категории</p>
      <p className="font-semibold">{`За ${d.window_days} дней ${d.companies} ${companies(d.companies ?? 0)} искали «${d.category}». Чаще всего просят:`}</p>
      <ul className="mt-1 list-disc pl-5 text-sm">
        {d.top.map((t) => <li key={t.tech}>{`${t.tech}: ${Math.round(t.share * 100)}% (${STATE[t.state]})`}</li>)}
      </ul>
      {d.skills.map((s) => (
        <Link key={s.code} to="/candidate/skills" className="mt-2 block text-sm font-semibold text-primary hover:underline">{`Подтвердите навык «${s.title}»`}</Link>
      ))}
    </Card>
  )
}
