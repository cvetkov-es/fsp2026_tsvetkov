import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { GRADE_TITLE, type Grade } from '../../api/assessment'
import { getMap } from '../../api/employer'
import { Card, ErrorText, Page, PageHeader } from '../../components/ui'

const SPECS = [['backend', 'Backend'], ['frontend', 'Frontend'], ['data', 'Data / Analytics']] as const
const GRADES: Grade[] = ['junior', 'middle', 'senior']

/** Насыщенность — по числу подтвердивших грейд относительно самой полной ячейки (08-map.png).
 *  Самая тёмная ячейка — средний синий (L 0,64): тёмный текст читается везде (контраст ≥ 5:1), а близкие числа выглядят близко. */
function heat(confirmed: number, max: number) {
  const t = Math.min(1, confirmed / max)
  return { t, background: `oklch(${(0.97 - 0.33 * t).toFixed(3)} ${(0.02 + 0.12 * t).toFixed(3)} 264)` }
}

export default function MapPage() {
  const q = useQuery({ queryKey: ['map'], queryFn: getMap })
  const cell = (s: string, g: Grade) => q.data?.cells.find((c) => c.specialization === s && c.grade === g)
  const max = Math.max(1, ...(q.data?.cells.map((c) => c.confirmed) ?? []))
  return (
    <Page>
      <PageHeader title="Карта категорий"
        description="Сколько кандидатов открыто для предложений в каждой категории. Чем насыщеннее ячейка, тем больше в ней подтвердивших грейд." />
      {q.isPending && <p>Загрузка…</p>}
      <ErrorText>{q.isError ? 'Не удалось загрузить карту' : null}</ErrorText>
      {q.data && (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-separate border-spacing-2.5">
            <thead><tr><th className="w-40" />{GRADES.map((g) => <th key={g} className="px-1 pb-1 text-left text-[13px] font-semibold text-muted">{GRADE_TITLE[g]}</th>)}</tr></thead>
            <tbody>{SPECS.map(([s, title]) => (
              <tr key={s}>
                <th scope="row" className="text-left text-base font-semibold">{title}</th>
                {GRADES.map((g) => {
                  const c = cell(s, g) ?? { confirmed: 0, unconfirmed: 0 }
                  const h = heat(c.confirmed, max)
                  const share = c.confirmed + c.unconfirmed ? Math.round((c.confirmed / (c.confirmed + c.unconfirmed)) * 100) : 0
                  return (
                    <td key={g}>
                      <Link to={`/employer/map/${s}/${g}`} style={{ background: h.background }} data-heat={h.t.toFixed(2)}
                        className="flex min-h-[120px] flex-col gap-3.5 rounded-[14px] p-[18px] text-ink transition hover:-translate-y-0.5">
                        <span className="flex items-baseline gap-2"><span className="text-[34px] font-semibold tracking-[-0.03em]">{c.confirmed}</span><span className="text-[13px]">подтверждены</span></span>
                        <span className="mt-auto flex flex-col gap-1.5">
                          <span className="h-1 overflow-hidden rounded-sm bg-white/60"><span className="block h-full bg-primary" style={{ width: `${share}%` }} /></span>
                          <span className="text-xs">+{c.unconfirmed} не подтвердили</span>
                        </span>
                      </Link>
                    </td>
                  )
                })}
              </tr>
            ))}</tbody>
          </table>
        </Card>
      )}
    </Page>
  )
}
