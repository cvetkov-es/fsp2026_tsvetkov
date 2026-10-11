import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, ApiError } from '../../api/client'
import {
  ACTIVE, acceptInvitation, blockCompany, counterInvitation, DECLINE_TITLE, declineInvitation, getBlocks, getMyInvitations, revokeContacts, rub,
  STATUS_TITLE, unblockCompany, viewInvitation, type ContactStatus, type DeclineReason, type GrossNet, type Invitation,
} from '../../api/contacts'
import { conditionalAccept, conditionalWithdraw } from '../../api/groups'
import { Button, Card, ErrorText, Input, LinkButton, Page, PageHeader, Pill, Select, type PillTone } from '../../components/ui'
import { linkClass } from '../../components/ui-classes'

type ConsentText = { type: string; title: string; body: string }
const net = (inv: Invitation) => inv.gross_net === 'gross' ? 'до вычета' : 'на руки'
const shortDay = (iso: string) => new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
const members = (n: number) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? 'участник' : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? 'участника' : 'участников'}`
const tone = (s: ContactStatus): PillTone => (s === 'accepted' ? 'success' : s === 'sent' || s === 'offer_v2' ? 'primary' : 'neutral')

const CONDITIONAL_TEXT: Record<string, string> = {
  open: 'Вы согласились условно. Контакты не переданы. Если наберётся минимальный состав, компания пришлёт личное приглашение.',
  min_reached: 'Срок вышел, минимальный состав набран. Компания пришлёт вам личное приглашение. Контакты пока не переданы.',
  not_reached: 'Срок вышел, минимальный состав не набран. Личного приглашения не будет. Можно отозвать согласие или отказаться.',
  ended: 'Срок вышел. Если компания пришлёт личное приглашение, оно появится здесь. Контакты пока не переданы.',
  closed: 'Групповое приглашение закрыто.',
}
const DANGER = 'text-sm font-medium text-danger hover:underline'

function GroupLine({ inv }: { inv: Invitation }) {
  const g = inv.group
  if (!g) return null
  return (
    <p className="mt-1 text-[13px] text-muted">
      {`Командное приглашение: команда «${g.team_name}», ${members(g.size)}, минимум ${g.min_size}, ответ до ${shortDay(g.deadline)}`}
      {g.min_reached_now !== null && <span className="ml-2">{g.min_reached_now ? '· минимальный состав набран' : '· минимальный состав пока не набран'}</span>}
    </p>
  )
}

function Compare({ items }: { items: Invitation[] }) {
  const rows: [string, (i: Invitation) => string][] = [
    ['Компания', (i) => `${i.company.name} · уровень ${i.company.trust_level}`], ['Потребность', (i) => i.need_title],
    ['Вилка', (i) => `${rub(i.salary_from)} – ${rub(i.salary_to)} ${net(i)}`], ['Максимум на руки', (i) => rub(i.salary_to_net)],
    ['Почему вы', (i) => i.why_you], ['Следующий шаг', (i) => i.next_step], ['Ответить до', (i) => new Date(i.expires_at).toLocaleDateString('ru-RU')],
  ]
  return (
    <div className="overflow-x-auto"><table className="w-full min-w-[600px] text-left text-sm">
      <tbody>{rows.map(([title, get]) => (
        <tr key={title} className="border-t border-line-soft align-top first:border-t-0">
          <th className="w-44 px-6 py-3 text-[13px] font-normal text-muted">{title}</th>
          {items.map((i) => <td key={i.id} className="px-4 py-3 leading-snug">{get(i)}</td>)}
        </tr>
      ))}</tbody>
    </table></div>
  )
}

function Actions({ inv, onDone }: { inv: Invitation; onDone: () => void }) {
  const texts = useQuery({ queryKey: ['consent-texts'], queryFn: () => api<{ texts: ConsentText[] }>('/consents/texts') })
  const consent = texts.data?.texts.find((t) => t.type === 'contact_transfer')
  const [agree, setAgree] = useState(false)
  const [reason, setReason] = useState<DeclineReason>('salary')
  const [comment, setComment] = useState('')
  const [confirmBlock, setConfirmBlock] = useState(false)
  const [amount, setAmount] = useState(0)
  const [gn, setGn] = useState<GrossNet>(inv.gross_net)
  const [error, setError] = useState<string | null>(null)
  const run = async (f: () => Promise<unknown>) => { setError(null); try { await f(); onDone() } catch (e) { setError(e instanceof ApiError ? e.title : 'Не удалось выполнить действие') } }
  const grouped = !!inv.group && inv.status !== 'offer_v2'  // до оффера v2 в командном приглашении — только условный ответ
  if (inv.status === 'conditionally_accepted') {
    return (
      <div className="space-y-2 border-t border-line-soft pt-4 text-sm">
        <p>{CONDITIONAL_TEXT[inv.group?.state ?? 'open'] ?? CONDITIONAL_TEXT.open}</p>
        {inv.group?.state !== 'min_reached' && inv.group?.state !== 'closed' && (
          <div className="flex gap-4">
            <button className={DANGER} onClick={() => run(() => conditionalWithdraw(inv.id))}>Отозвать согласие</button>
            {inv.group?.state !== 'open' && (
              <button className={DANGER} onClick={() => run(() => declineInvitation(inv.id, 'other', ''))}>Отказаться</button>
            )}
          </div>
        )}
        <ErrorText>{error}</ErrorText>
      </div>
    )
  }
  if (!['sent', 'viewed', 'offer_v2'].includes(inv.status)) return null
  return (
    <div className="space-y-3 border-t border-line-soft pt-5 text-sm">
      {grouped ? (
        <div className="space-y-2.5 rounded-xl bg-surface-2 p-4">
          <p className="text-[13px] text-muted">Контакты пока не передаются. Если к сроку наберётся минимальный состав, компания пришлёт личное приглашение. Тогда вы решите, передавать ли контакты.</p>
          <Button onClick={() => run(() => conditionalAccept(inv.id))}>Согласиться условно</Button>
        </div>
      ) : (
        <div className="space-y-3">
          <label className="flex gap-2.5 leading-snug"><input type="checkbox" className="mt-0.5" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
            <span>{consent ? consent.title : 'Согласие на передачу контактов компании'}: передать ФИО и контакты компании «{inv.company.name}»</span></label>
          {consent && <details className="text-xs text-muted"><summary className={`cursor-pointer ${linkClass}`}>Текст согласия</summary>{consent.body}</details>}
          <Button size="lg" className="w-full sm:w-auto" disabled={!agree} onClick={() => run(() => acceptInvitation(inv.id))}>Принять приглашение</Button>
        </div>
      )}
      {inv.version === 1 && !grouped && (
        <div className="flex flex-wrap items-end gap-2 rounded-xl bg-surface-2 p-3">
          <label className="flex min-w-[140px] flex-1 flex-col gap-1 text-xs text-muted">Встречное условие, ₽
            <Input aria-label="Сумма встречного условия" inputMode="numeric" value={amount || ''} onChange={(e) => setAmount(Number(e.target.value.replace(/\D/g, '')))} /></label>
          <Select aria-label="Встречное условие: до вычета или на руки" className="w-auto" value={gn} onChange={(e) => setGn(e.target.value as GrossNet)}>
            <option value="gross">до вычета</option><option value="net">на руки</option>
          </Select>
          <Button type="button" variant="dark" disabled={!amount} onClick={() => run(() => counterInvitation(inv.id, amount, gn))}>Предложить сумму (один раз)</Button>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2 rounded-xl bg-danger-soft p-3">
        <Select aria-label="Причина отказа" className="w-auto min-w-[180px] flex-1 border-danger-line" value={reason} onChange={(e) => setReason(e.target.value as DeclineReason)}>
          {(Object.keys(DECLINE_TITLE) as DeclineReason[]).map((r) => <option key={r} value={r}>{DECLINE_TITLE[r]}</option>)}
        </Select>
        <Input aria-label="Комментарий к отказу" className="min-w-[160px] flex-1 border-danger-line" placeholder="Комментарий (необязательно)" maxLength={500} value={comment} onChange={(e) => setComment(e.target.value)} />
        <Button variant="danger" onClick={() => run(() => declineInvitation(inv.id, reason, comment))}>Отклонить</Button>
      </div>
      {confirmBlock ? (
        <p className="text-xs">Компания «{inv.company.name}» больше не сможет присылать приглашения. Вернуть можно в списке скрытых компаний.{' '}
          <button className="font-semibold text-danger hover:underline" onClick={() => run(() => blockCompany(inv.company.id))}>Да, скрыть</button>{' '}
          <button className="text-muted hover:underline" onClick={() => setConfirmBlock(false)}>Отмена</button></p>
      ) : <button className="text-[13px] text-subtle hover:text-ink" onClick={() => setConfirmBlock(true)}>Не показывать эту компанию</button>}
      <ErrorText>{error}</ErrorText>
    </div>
  )
}

/** Приглашения кандидата (05-invitations.png): карточки с вилкой и статусом, раскрытие с «Почему вы», сравнение офферов. */
export default function InvitationsPage() {
  const qc = useQueryClient()
  const list = useQuery({ queryKey: ['my-invitations'], queryFn: getMyInvitations })
  const [open, setOpen] = useState<string | null>(null)
  const [compare, setCompare] = useState<string[]>([])
  const blocks = useQuery({ queryKey: ['blocks'], queryFn: getBlocks })
  const reload = () => { void qc.invalidateQueries({ queryKey: ['my-invitations'] }); void qc.invalidateQueries({ queryKey: ['blocks'] }) }
  const items = list.data ?? []
  const chosen = items.filter((i) => compare.includes(i.id))
  return (
    <Page narrow>
      <PageHeader title="Приглашения" actions={<span className="text-sm text-muted">Отметьте два приглашения или больше, чтобы сравнить</span>} />
      {items.length === 0 && <Card><p>Приглашений пока нет. Чтобы их получать, откройте профиль для предложений.</p></Card>}
      {chosen.length >= 2 && (
        <Card as="section" className="overflow-hidden p-0">
          <div className="flex items-center justify-between border-b border-line-soft px-6 py-4">
            <h2 className="font-semibold">Сравнение приглашений</h2>
            <button className="text-[13px] text-muted hover:text-ink" onClick={() => setCompare([])}>Сбросить</button>
          </div>
          <Compare items={chosen} />
        </Card>
      )}
      {items.map((inv) => (
        <Card as="article" key={inv.id} className={`space-y-4 ${open === inv.id ? 'border-primary' : ''}`}>
          <div className="flex flex-wrap items-center gap-3.5">
            <span aria-hidden="true" className="grid size-11 shrink-0 place-items-center rounded-xl bg-ink font-semibold text-white">{inv.company.name.slice(0, 1)}</span>
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{inv.company.name} <span className="text-xs font-normal text-muted">· уровень доверия {inv.company.trust_level}</span></p>
              <p className="mt-0.5 text-[13px] text-muted">{inv.need_title} · {rub(inv.salary_from)} – {rub(inv.salary_to)} {net(inv)}</p>
              <GroupLine inv={inv} />
            </div>
            <div className="flex items-center gap-3">
              {ACTIVE.includes(inv.status) && (
                <label className="flex items-center gap-1.5 text-xs text-muted"><input type="checkbox" checked={compare.includes(inv.id)} onChange={() => setCompare((c) => c.includes(inv.id) ? c.filter((x) => x !== inv.id) : [...c, inv.id])} />сравнить</label>
              )}
              <Pill tone={tone(inv.status)}>{STATUS_TITLE[inv.status]}</Pill>
            </div>
          </div>
          {open === inv.id ? (
            <div className="space-y-4 text-sm">
              <div>
                <p className="text-3xl font-semibold tracking-[-0.025em]">{rub(inv.salary_from)} – {rub(inv.salary_to)}</p>
                <p className="mt-1 text-[13px] text-muted">{net(inv)} · до {rub(inv.salary_to_net)} на руки</p>
              </div>
              <div className="rounded-xl bg-surface-2 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.05em] text-muted">Почему вы</p>
                <p className="mt-1.5 text-[15px] leading-relaxed">{inv.why_you}</p>
              </div>
              {inv.description && <p className="leading-relaxed">{inv.description}</p>}
              <div className="grid gap-3.5 sm:grid-cols-2">
                <div><p className="text-xs text-muted">Следующий шаг</p><p className="mt-1 font-medium leading-snug">{inv.next_step}</p></div>
                <div><p className="text-xs text-muted">Ответить до</p><p className="mt-1 font-medium">{new Date(inv.expires_at).toLocaleDateString('ru-RU')}</p></div>
              </div>
              {inv.status === 'countered' && <p>Ваше встречное условие: {rub(inv.counter_amount ?? 0)}. Ждём ответа компании.</p>}
              <Actions inv={inv} onDone={reload} />
            </div>
          ) : (
            <Button variant="secondary" size="sm" onClick={async () => { setOpen(inv.id); if (inv.status === 'sent') { await viewInvitation(inv.id); reload() } }}>Открыть</Button>
          )}
          {inv.status === 'conditionally_accepted' && open !== inv.id && <Actions inv={inv} onDone={reload} />}  {/* отзыв согласия виден без раскрытия карточки */}
          {inv.chat_open && (
            <div className="flex flex-wrap gap-2 border-t border-line-soft pt-4">
              <LinkButton to={`/contacts/${inv.id}`} variant="dark">Чат с компанией</LinkButton>
              <Button variant="secondary" className="text-muted" onClick={async () => { await revokeContacts(inv.id); reload() }}>Скрыть контакты и уведомить компанию</Button>
            </div>
          )}
        </Card>
      ))}
      {blocks.data && blocks.data.length > 0 && (
        <Card as="section" className="space-y-2">
          <h2 className="text-lg font-semibold">Скрытые компании</h2>
          <ul className="divide-y divide-line-soft text-sm">{blocks.data.map((b) => (
            <li key={b.id} className="flex items-center justify-between gap-2 py-2"><span>{b.name}</span>
              <button className={linkClass} onClick={async () => { await unblockCompany(b.id); reload() }}>вернуть</button></li>
          ))}</ul>
        </Card>
      )}
    </Page>
  )
}
