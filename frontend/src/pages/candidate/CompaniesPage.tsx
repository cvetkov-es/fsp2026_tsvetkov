import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { errorText } from '../../api/errors'
import { getCompanies, sendSignal, withdrawSignal, type CompanyItem } from '../../api/initiative'
import LoadError from '../../components/LoadError'
import { Button, Card } from '../../components/ui'

function CompanyCard({ c, canSend, onChanged }: { c: CompanyItem; canSend: boolean; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null)
  const run = async (f: () => Promise<unknown>) => {
    setError(null)
    try { await f(); onChanged() } catch (e) { setError(errorText(e)) }
  }
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">{c.name}</h2>
        {c.trust_level === 'L0'
          ? <span className="rounded-full bg-line-soft px-2 py-0.5 text-xs text-ink">не проверена</span>
          : <span className="rounded-full bg-line-soft px-2 py-0.5 text-xs text-ink">уровень {c.trust_level}</span>}
      </div>
      {c.industry && <p className="text-sm text-muted">{c.industry}</p>}
      {c.description && <p className="mt-1 text-sm">{c.description}</p>}
      <p className="mt-1 text-xs text-muted">{`открытых потребностей: ${c.open_needs}`}</p>
      <div className="mt-3">
        {c.signal_id
          ? <button className="text-sm font-semibold text-primary hover:underline" onClick={() => run(() => withdrawSignal(c.signal_id!))}>Интерес отмечен · отменить</button>
          : <Button disabled={!canSend} onClick={() => run(() => sendSignal(c.id))}>Хочу к вам</Button>}
      </div>
      {error && <p role="alert" className="mt-2 text-sm text-danger">{error}</p>}
    </Card>
  )
}

/** «Хочу к вам» (процесс 2.9): сигнал видит только компания, в её подборке готовность кандидата поднимается. */
export default function CompaniesPage() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['companies'], queryFn: getCompanies })
  const reload = () => { void qc.invalidateQueries({ queryKey: ['companies'] }) }
  const d = q.data
  return (
    <div className="space-y-4 p-6">
      <h1 className="text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">Компании: «Хочу к вам»</h1>
      {q.isError && <LoadError error={q.error} />}
      {d && (
        <>
          <p className="font-semibold">{`Осталось отметок в этом квартале: ${d.signals_left} из ${d.signals_limit}`}</p>
          <p className="text-sm text-muted">Компания увидит ваш интерес, и вы будете выше в её подборке. Отметку можно отменить, но она останется потраченной.</p>
          <p className="text-sm text-muted">Компания увидит отметку, если вы прошли тест и профиль открыт для предложений.</p>
          {d.signals_left === 0 && <p className="text-sm text-danger">Отметки на этот квартал закончились. Новые появятся в следующем квартале.</p>}
          {d.items.length === 0 && <Card><p>Пока нет компаний с открытыми потребностями.</p></Card>}
          {d.items.map((c) => <CompanyCard key={c.id} c={c} canSend={d.signals_left > 0} onChanged={reload} />)}
        </>
      )}
    </div>
  )
}
