import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { FSP_LINK_URL, fspErrorText, getFsp, unlinkFsp, type FspProfile } from '../../api/fsp'
import { Card, Notice } from '../ui'
import { linkClass } from '../ui-classes'

const date = (iso: string) => new Date(iso).toLocaleDateString('ru-RU')

/** ФСП в профиле (процесс 2.7): без истории — нейтрально, уровни по таблице 6.2, онлайн-отборы одной строкой. */
export function FspView({ fsp, onUnlink }: { fsp: FspProfile; onUnlink: () => void }) {
  const linked = fsp.status === 'LINKED' || fsp.status === 'LINKED_EMPTY' || fsp.status === 'SYNC_STALE'
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Достижения ФСП</h2>
        <div className="flex gap-3 text-sm">
          <a className={linkClass} href={FSP_LINK_URL}>{linked ? 'Обновить из ФСП' : 'Привязать FSP ID'}</a>
          {linked && <button className="text-sm text-muted hover:text-ink" onClick={onUnlink}>Отвязать и скрыть данные ФСП</button>}
        </div>
      </div>
      {fsp.status === 'NOT_LINKED' && <p className="mt-2 text-sm">Результатов ФСП пока нет. Если вы участвовали в соревнованиях ФСП, привяжите FSP ID: результаты появятся сами.</p>}
      {fsp.status === 'CONSENT_REVOKED' && <p className="mt-2 text-sm">{fsp.login_via_fsp
        ? 'Данные ФСП удалены. Входить через FSP ID можно, как раньше. Чтобы вернуть данные, нажмите «Привязать FSP ID».'
        : 'Данные ФСП удалены по вашему запросу. Привязать FSP ID можно снова.'}</p>}
      {fsp.status === 'LINKED_EMPTY' && <p className="mt-2 text-sm">FSP ID привязан, результатов в реестре ФСП пока нет.</p>}
      {fsp.status === 'SYNC_STALE' && <Notice tone="warning" className="mt-2">{fsp.last_sync_at
        ? `ФСП сейчас недоступен. Показаны данные на ${date(fsp.last_sync_at)}.`
        : 'Данные ФСП ещё не пришли. Нажмите «Обновить из ФСП» чуть позже.'}</Notice>}
      {fsp.summary && <p className="mt-2 font-semibold">{fsp.summary}</p>}
      {fsp.results.length > 0 && (
        <ul className="mt-2 space-y-1 text-sm">{fsp.results.map((r) => (
          <li key={`${r.competition_title}-${r.date}`} className={r.counted ? '' : 'text-subtle'}>
            {r.competition_title} · {r.tier_title}{r.place ? `, ${r.place} место${r.field_size ? ` из ${r.field_size}` : ''}` : ''}
            {r.team_name ? ` · в составе команды «${r.team_name}» (${r.team_size} чел.)` : ''}{r.note ? ` · не засчитано: ${r.note}` : ''}
          </li>
        ))}</ul>
      )}
      {fsp.online.count > 0 && <p className="mt-1 text-sm">Онлайн-отборов: {fsp.online.count}, дисциплин: {fsp.online.disciplines}. По каждой дисциплине засчитываем один результат.</p>}
      {fsp.ranks.length > 0 && <p className="mt-1 text-sm">{fsp.ranks.map((k) => `${k.title}: ${k.valid ? (k.valid_until ? `действует до ${date(k.valid_until)}` : 'бессрочно') : 'срок истёк'}`).join(' · ')}</p>}
    </Card>
  )
}

export function FspSection() {
  const qc = useQueryClient()
  const [params, setParams] = useSearchParams()
  const q = useQuery({ queryKey: ['fsp'], queryFn: getFsp })
  // Итог возврата из FSP ID показывается один раз: параметры убираются из адреса, обновление страницы его не повторит
  const [linked] = useState(() => params.get('fsp') === 'linked')
  const [error] = useState(() => fspErrorText(params.get('fsp_error')))
  useEffect(() => {
    if (!params.has('fsp') && !params.has('fsp_error')) return
    const next = new URLSearchParams(params)
    next.delete('fsp')
    next.delete('fsp_error')
    setParams(next, { replace: true })
  }, [params, setParams])
  return (
    <div className="space-y-2">
      {linked && <Notice tone="success">FSP ID привязан, результаты обновлены.</Notice>}
      {error && <Notice tone="danger" role="alert">{error}</Notice>}
      {q.data && <FspView fsp={q.data} onUnlink={async () => { await unlinkFsp(); await qc.invalidateQueries({ queryKey: ['fsp'] }) }} />}
    </div>
  )
}
