import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { ApiError } from '../api/client'
import { getLabLatest, getLabRun, startLabRun, type AiPolicies, type Headline, type LabResults, type RunBrief } from '../api/lab'
import { useAuth } from '../auth/AuthContext'
import { NdcgChart, OcChart } from '../components/lab/Charts'
import { Button, Card, ErrorText, Notice, Page, PageHeader } from '../components/ui'

const MIN_POPULATION = 100
const pct = (v: number | null | undefined) => (v == null ? '—' : `${Math.round(v * 100)}%`)
const num = (v: number | null | undefined, digits = 2) => (v == null ? '—' : v.toFixed(digits))
const fmt = (h: Headline) => (h.format === 'percent' ? pct(h.value) : num(h.value))
const MARKET_TITLES: Record<string, string> = {
  ours: 'Наш: квота и «вилка в ожиданиях у X из Y»', no_fork_info: 'Без подсказки о вилке', no_quota: 'Без квоты', random_order: 'Случайный порядок',
}
const FAILURES: Record<string, string> = {
  stale: 'прогон висел дольше часа', worker_unavailable: 'фоновый обработчик не запущен, прогон не начался', worker_restarted: 'фоновый обработчик перезапустили во время прогона',
}
const RUN_STATUS: Record<string, string> = { queued: 'в очереди', running: 'считается' }
const isActive = (r: RunBrief) => r.status === 'queued' || r.status === 'running'

function AiPoliciesCard({ p }: { p: AiPolicies }) {
  return (
    <Card>
      <h2 className="mb-3 text-base font-semibold">«Работа с ИИ»: три политики</h2>
      <div className="overflow-x-auto"><table className="w-full min-w-[560px] text-left text-sm"><thead><tr><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Политика</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Подтверждено</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Точность</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Принятые ошибки ИИ</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Отклонённые верные</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Минут</th></tr></thead>
        <tbody>{p.policies.map((x) => (
          <tr key={x.key}><td className="border-t border-line-soft px-3 py-2.5">{x.title}</td><td className="border-t border-line-soft px-3 py-2.5">{pct(x.pass_rate)}</td><td className="border-t border-line-soft px-3 py-2.5">{pct(x.accuracy)}</td><td className="border-t border-line-soft px-3 py-2.5">{pct(x.miss_weighted)}</td><td className="border-t border-line-soft px-3 py-2.5">{pct(x.false_reject)}</td><td className="border-t border-line-soft px-3 py-2.5">{num(x.minutes, 0)}</td></tr>
        ))}</tbody></table></div>
      <p className="mt-2">{p.attempts} попыток на настоящих заданиях из банка. «Только второй ИИ» копирует ответы {p.model} и всегда уверен. «ИИ + проверка запуском» даёт те же ответы, но уверен там, где ломающий вход подтвердился. Время ИИ посчитано без копирования, поэтому это нижняя граница.</p>
      {p.llm === 'skipped' && <p>Политики со вторым ИИ считаются при прогоне с ключом доступа к ИИ.</p>}
    </Card>
  )
}

function Details({ r }: { r: LabResults }) {
  const rankerTitles: Record<string, string> = Object.fromEntries(r.charts.ndcg_bars.map((b) => [b.key, b.title]))
  const forkRaised = r.market.ours?.fork_raised_share
  return (
    <div className="space-y-4 text-sm">
      <Card>
        <h2 className="mb-3 text-base font-semibold">Тест по грейдам</h2>
        <div className="overflow-x-auto"><table className="w-full min-w-[560px] text-left text-sm"><thead><tr><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Грейд</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">N</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Ложные подтверждения</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Ложные отказы</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Длина (сред. / p90)</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Экспресс</th></tr></thead>
          <tbody>{Object.entries(r.test.by_grade).map(([g, v]) => (
            <tr key={g}><td className="border-t border-line-soft px-3 py-2.5">{g}</td><td className="border-t border-line-soft px-3 py-2.5">{v.n}</td><td className="border-t border-line-soft px-3 py-2.5">{pct(v.false_positive)}</td><td className="border-t border-line-soft px-3 py-2.5">{pct(v.false_negative)}</td><td className="border-t border-line-soft px-3 py-2.5">{num(v.len_full.mean, 1)} / {v.len_full.p90 ?? '—'}</td><td className="border-t border-line-soft px-3 py-2.5">{num(v.len_express.mean, 1)}</td></tr>
          ))}</tbody></table></div>
        <p className="mt-2">Повторный тест, κ по расстоянию до порога: {r.test.kappa_by_distance.map((b) => `${b.dist_from}–${b.dist_to ?? '∞'}: ${num(b.kappa)}`).join(' · ')}</p>
        <p>Экспресс-тест решает сам в {pct(r.test.express_decided_share)} случаев (точность {pct(r.test.accuracy_express_decided)}); остальным предлагаем продолжить до полного теста.</p>
        <p>При утечке {pct(r.test.leak.leaked_share)} банка ложные подтверждения: у статичного банка {pct(r.test.leak.static_bank_false_positive)}, у нашего {pct(r.test.leak.generated_bank_false_positive)}, у кандидата без утечки {pct(r.test.leak.honest_false_positive)}.</p>
      </Card>
      {r.ai_skill_policies && 'policies' in r.ai_skill_policies && <AiPoliciesCard p={r.ai_skill_policies} />}
      <Card>
        <h2 className="mb-3 text-base font-semibold">Подбор: скрытая истина, бейзлайны, проверки</h2>
        <div className="overflow-x-auto"><table className="w-full min-w-[560px] text-left text-sm"><thead><tr><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Ранжирование</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">nDCG@10</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">P@10</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">MRR</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">nDCG отложенная</th></tr></thead>
          <tbody>{Object.entries(r.matching.rankers).map(([k, v]) => (
            <tr key={k}><td className="border-t border-line-soft px-3 py-2.5">{rankerTitles[k] ?? k}</td><td className="border-t border-line-soft px-3 py-2.5">{num(v.all.ndcg.mean)}</td><td className="border-t border-line-soft px-3 py-2.5">{num(v.all.p_at_k.mean)}</td><td className="border-t border-line-soft px-3 py-2.5">{num(v.all.mrr.mean)}</td><td className="border-t border-line-soft px-3 py-2.5">{num(v.holdout.ndcg.mean)}</td></tr>
          ))}</tbody></table></div>
        <ul className="mt-2 list-disc pl-5">{r.matching.paired.map((c) => <li key={c.case}>{c.passed ? '✓' : '✗'} {c.case}</li>)}</ul>
        <p>Каждый кандидат в одном блоке: {r.matching.blocks.each_candidate_one_block ? 'да' : 'нет'} · неподтверждённый никогда не выше подтверждённого: {r.matching.blocks.unconfirmed_never_above_confirmed ? 'да' : 'нет'} · смена города не меняет порядок: {pct(r.matching.invariance.city_changed_same_order_share)} · смена псевдонима: {pct(r.matching.invariance.pseudonym_changed_same_order_share)}</p>
        <p>Справедливость (доля в топ-10 «без ФСП / с ФСП» при равной силе теста): {r.matching.fairness.by_test_tier.map((t) => num(t.ratio)).join(' · ')}. По ТЗ достижения ФСП дают преимущество. Доля «фармеров» онлайн-отборов в топ-10: {pct(r.matching.fairness.farmers_share_top10)} при {pct(r.matching.fairness.farmers_share_relevant)} среди релевантных.</p>
      </Card>
      <Card>
        <h2 className="mb-3 text-base font-semibold">Калибровка порогов и рынок</h2>
        <p>Экспертный порог смещён на {r.calibration.shift} логита. Ошибка после калибровки: {r.calibration.by_n.map((b) => `N=${b.n}: ${num(b.calibrated_error)}`).join(' · ')}.</p>
        <div className="overflow-x-auto"><table className="mt-2 w-full min-w-[560px] text-left text-sm"><thead><tr><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Вариант рынка</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Приглашений на потребность</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Принято</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Ниже порога</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">p95 на кандидата</th><th className="bg-surface-2 px-3 py-2.5 text-xs font-semibold text-subtle">Качество найма, 0–3</th></tr></thead>
          <tbody>{Object.entries(r.market).map(([k, v]) => (
            <tr key={k}><td className="border-t border-line-soft px-3 py-2.5">{MARKET_TITLES[k] ?? k}</td><td className="border-t border-line-soft px-3 py-2.5">{v.invites_per_need.toFixed(1)}</td><td className="border-t border-line-soft px-3 py-2.5">{pct(v.acceptance_rate)}</td><td className="border-t border-line-soft px-3 py-2.5">{pct(v.below_threshold_share)}</td><td className="border-t border-line-soft px-3 py-2.5">{v.invites_per_candidate_p95 ?? '—'}</td><td className="border-t border-line-soft px-3 py-2.5">{num(v.hired_relevance)}</td></tr>
          ))}</tbody></table></div>
        {forkRaised != null && (
          <p className="mt-2">{forkRaised === 0
            ? 'Подсказка «вилка в ожиданиях у X из Y» в этой популяции ни разу не сработала: вилки и так покрывают ожидания большинства. Поэтому строки «Наш» и «Без подсказки о вилке» совпадают.'
            : `Подсказка «вилка в ожиданиях у X из Y» убедила поднять вилку в ${pct(forkRaised)} потребностей.`}</p>
        )}
      </Card>
    </div>
  )
}

export default function LabPage() {
  const { me } = useAuth()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['lab'], queryFn: getLabLatest })
  const active = q.data?.active ?? null
  // Пока прогон идёт, опрашиваем только его статус; весь отчёт перечитываем, когда прогон закончился
  const poll = useQuery({ queryKey: ['lab-run', active?.id], queryFn: () => getLabRun(active?.id ?? ''), enabled: !!active, refetchInterval: 10_000 })
  useEffect(() => {
    if (active && poll.data?.id === active.id && !isActive(poll.data)) void qc.invalidateQueries({ queryKey: ['lab'] })
  }, [active, poll.data, qc])
  const [population, setPopulation] = useState('500')
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const max = q.data?.max_population ?? 3000
  const r = q.data?.results
  const failed = q.data?.failed
  const current = poll.data && active && poll.data.id === active.id ? poll.data : active
  const start = async () => {
    setError(null)
    const n = Number(population)
    if (!Number.isInteger(n) || n < MIN_POPULATION || n > max) {
      setError(`Размер популяции: целое число от ${MIN_POPULATION} до ${max}`)
      return
    }
    setStarting(true)
    try {
      await startLabRun(n)
      await qc.invalidateQueries({ queryKey: ['lab'] })
    } catch (e) {
      setError(e instanceof ApiError ? e.title : 'Не удалось запустить прогон')
    } finally {
      setStarting(false)
    }
  }
  const runControl = current
    ? <p className="text-sm text-muted">Идёт прогон на {current.population} кандидатов ({RUN_STATUS[current.status] ?? current.status}). Обычно до минуты — страница обновится сама.</p>
    : me
      ? (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-white py-1.5 pl-3.5 pr-1.5">
          <label htmlFor="lab-population" className="text-[13px] text-muted">Размер популяции</label>
          <input id="lab-population" type="number" min={MIN_POPULATION} max={max} step={100}
            className="w-24 rounded-lg border border-line px-2 py-1.5 font-mono text-[13px]" value={population} onChange={(e) => setPopulation(e.target.value)} />
          <Button variant="dark" size="sm" disabled={starting} onClick={() => void start()}>Запустить прогон</Button>
          <span className="text-xs text-subtle">пересчитает тест и подбор, обычно до минуты</span>
        </div>
      )
      : <p className="text-sm text-muted">Чтобы запустить свой прогон, войдите.</p>
  return (
    <Page>
      <PageHeader title="Лаборатория"
        description="Здесь мы проверяем тест и подбор на синтетических кандидатах, у которых заранее известен настоящий уровень."
        actions={q.isSuccess ? runControl : null} />
      <div className="space-y-1 font-mono text-xs text-subtle">
        {q.data?.run && <p>Прогон от {new Date(q.data.run.finished_at ?? q.data.run.created_at).toLocaleString('ru-RU')} · популяция {q.data.run.population}</p>}
        {q.isSuccess && me && !current && <p>Прогон идёт в фоне и не обращается к ИИ. Результат появится на этой странице.</p>}
      </div>
      <ErrorText>{error}</ErrorText>
      {q.isLoading && <p>Загрузка…</p>}
      <ErrorText>{q.isError ? (q.error instanceof ApiError ? q.error.title : 'Не удалось загрузить результаты лаборатории') : null}</ErrorText>
      {failed && (
        <Notice tone="warning" role="alert">
          Прогон на {failed.population} кандидатов не завершился: {FAILURES[failed.error ?? ''] ?? `ошибка ${failed.error ?? ''}`.trim()}.{r ? ' Ниже последний успешный результат.' : ''}
        </Notice>
      )}
      {q.isSuccess && !r && <Card><p>Прогонов пока нет. {me ? 'Запустите прогон кнопкой выше.' : 'Войдите, чтобы запустить прогон.'}</p></Card>}
      {r && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{r.headline.map((h) => (
            <Card key={h.key} className="flex flex-col gap-1.5 p-5">
              <p className="text-4xl font-semibold tracking-[-0.03em] text-primary">{fmt(h)}</p>
              <p className="text-sm font-semibold">{h.title}</p>
              <p className="text-xs leading-snug text-muted">{h.note}</p>
            </Card>
          ))}</div>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card><h2 className="mb-4 text-base font-semibold">Как решает тест</h2><OcChart points={r.charts.oc_curve} /></Card>
            <Card><h2 className="mb-4 text-base font-semibold">Качество подборки против бейзлайнов · nDCG@10</h2><NdcgChart bars={r.charts.ndcg_bars} /></Card>
          </div>
          <Details r={r} />
        </>
      )}
    </Page>
  )
}
