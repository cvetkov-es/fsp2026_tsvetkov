import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { getNeedInvitations, getQuota, respondCounter, rub, STATUS_TITLE, withdrawInvitation, type EmployerInvitation } from '../../api/contacts'
import { getNeed } from '../../api/employer'
import { BackLink, Button, Card, ErrorText, Input, LinkButton, Meter, Page, PageHeader, Pill } from '../../components/ui'

function CounterResponse({ inv, onDone }: { inv: EmployerInvitation; onDone: () => void }) {
  const [from, setFrom] = useState(inv.salary_from)
  const [to, setTo] = useState(Math.max(inv.salary_to, inv.counter_amount ?? 0))
  const [error, setError] = useState<string | null>(null)
  const run = async (body: Parameters<typeof respondCounter>[1]) => {
    try { await respondCounter(inv.id, body); onDone() } catch (e) { setError(e instanceof ApiError ? e.title : 'Не удалось отправить ответ') }
  }
  return (
    <div className="mt-2 space-y-2 rounded-xl bg-surface-2 p-4 text-sm">
      <p>Встречное условие: {rub(inv.counter_amount ?? 0)} ({inv.gross_net === 'gross' ? 'до вычета' : 'на руки'}){inv.counter_comment ? `. Комментарий: «${inv.counter_comment}»` : ''}</p>
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs">от <Input aria-label="Новая вилка от" inputMode="numeric" value={from} onChange={(e) => setFrom(Number(e.target.value.replace(/\D/g, '')))} /></label>
        <label className="text-xs">до <Input aria-label="Новая вилка до" inputMode="numeric" value={to} onChange={(e) => setTo(Number(e.target.value.replace(/\D/g, '')))} /></label>
        <Button type="button" disabled={from > to} onClick={() => run({ action: 'offer_v2', salary_from: from, salary_to: to })}>Предложить новую вилку</Button>
        <Button type="button" variant="danger" size="sm" onClick={() => run({ action: 'decline' })}>Отклонить условие</Button>
      </div>
      <ErrorText>{error}</ErrorText>
    </div>
  )
}

export default function NeedInvitationsPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const need = useQuery({ queryKey: ['need', id], queryFn: () => getNeed(id) })
  const list = useQuery({ queryKey: ['need-invitations', id], queryFn: () => getNeedInvitations(id) })
  const quota = useQuery({ queryKey: ['quota', id], queryFn: () => getQuota(id) })
  const reload = () => { void qc.invalidateQueries({ queryKey: ['need-invitations', id] }); void qc.invalidateQueries({ queryKey: ['quota', id] }) }
  return (
    <Page>
      <PageHeader back={<BackLink to={`/employer/needs/${id}`}>к подборке</BackLink>} title={`Приглашения · ${need.data?.title ?? ''}`}
        actions={<LinkButton to={`/employer/needs/${id}/board`} variant="secondary" size="sm">Доска найма</LinkButton>} />
      {quota.data && (
        <Card className="space-y-2 p-4">
          <p className="text-sm text-muted">Квота: ответа ждут {quota.data.used} из {quota.data.limit} приглашений</p>
          {quota.data.limit > 0 && <Meter value={quota.data.used / quota.data.limit} label="Квота приглашений" />}
        </Card>
      )}
      {list.data?.length === 0 && <Card><p>Приглашений пока нет. Отправить их можно из подборки.</p></Card>}
      {list.data?.map((inv) => (
        <Card key={inv.id}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-mono font-bold">{inv.alias}</span>
            <Pill tone={inv.status === 'accepted' ? 'success' : ['declined', 'company_declined', 'expired', 'withdrawn', 'revoked'].includes(inv.status) ? 'neutral' : 'primary'}>{STATUS_TITLE[inv.status]}{inv.version > 1 ? ' · версия 2' : ''}{inv.status === 'offer_v2' && inv.viewed ? ' · просмотрено' : ''}</Pill>
          </div>
          <p className="mt-1 text-sm">{rub(inv.salary_from)} – {rub(inv.salary_to)} {inv.gross_net === 'gross' ? 'до вычета' : 'на руки'} · до {new Date(inv.expires_at).toLocaleDateString('ru-RU')}{inv.hours_per_week ? ` · ${inv.hours_per_week} ч в неделю` : ''}</p>
          {inv.decline_reason && <p className="text-sm text-muted">Причина: {inv.decline_reason}</p>}
          {inv.status === 'countered' && <CounterResponse inv={inv} onDone={reload} />}
          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
            {inv.chat_open && <LinkButton to={`/contacts/${inv.id}`} variant="secondary" size="sm">Контакты и чат</LinkButton>}
            {['sent', 'viewed', 'offer_v2', 'countered', 'conditionally_accepted'].includes(inv.status) && (
              <Button variant="ghost" size="sm" onClick={async () => { await withdrawInvitation(inv.id); reload() }}>Отозвать</Button>
            )}
          </div>
        </Card>
      ))}
    </Page>
  )
}
