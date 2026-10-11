import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { GRADE_TITLE } from '../../api/assessment'
import { ACTIVE, getQuota, STATUS_TITLE } from '../../api/contacts'
import { closeNeed, FORMAT_TITLE, getNeed, getSelection, pin, SKILL_TITLE, unpin, type Card as CardData, type Filters, type Format, type Selection } from '../../api/employer'
import { CandidateCard } from '../../components/employer/CandidateCard'
import { InviteForm } from '../../components/employer/InviteForm'
import { BackLink, Button, Card, Chip, LinkButton, Page, PageHeader } from '../../components/ui'
import { linkClass } from '../../components/ui-classes'

/** «−63 выбыли (не проходит: нет Kafka, 63 чел.)»: причины сгруппированы, псевдонимы — под раскрытием. */
function DiffCard({ diff }: { diff: NonNullable<Selection['diff']> }) {
  const groups = new Map<string, number>()
  for (const r of diff.removed) groups.set(r.reason, (groups.get(r.reason) ?? 0) + 1)
  const reasons = [...groups].map(([reason, n]) => `${reason}, ${n} чел.`).join('; ')
  return (
    <Card tone="success" className="p-4 sm:px-[18px]">
      <p className="text-xs text-success">С последнего просмотра</p>
      <p className="mt-1 text-lg font-semibold text-success-ink">+{diff.added} новых, −{diff.removed.length} выбыли{reasons ? ` (${reasons})` : ''}</p>
      {diff.removed.length > 0 && (
        <details className="mt-1 text-sm"><summary className={`cursor-pointer ${linkClass}`}>кто выбыл</summary>
          <p className="mt-1 font-mono text-xs">{diff.removed.map((r) => r.alias).join(', ')}</p></details>
      )}
    </Card>
  )
}

type Inviting = { ref: string; place: 'list' | 'short' } | null

export default function SelectionPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const nav = useNavigate()
  const need = useQuery({ queryKey: ['need', id], queryFn: () => getNeed(id) })
  const [f, setF] = useState<Filters>({})
  const sel = useQuery({ queryKey: ['selection', id, f], queryFn: () => getSelection(id, f) })
  const quota = useQuery({ queryKey: ['quota', id], queryFn: () => getQuota(id) })
  const [inviting, setInviting] = useState<Inviting>(null)
  const toggle = <T,>(arr: T[] | undefined, v: T) => ((arr ?? []).includes(v) ? (arr ?? []).filter((x) => x !== v) : [...(arr ?? []), v])
  const onPin = async (ref: string, p: boolean) => { await (p ? pin(id, ref) : unpin(id, ref)); await qc.invalidateQueries({ queryKey: ['selection', id] }) }
  const canInvite = (c: CardData) => c.contact_status == null || (!ACTIVE.includes(c.contact_status) && c.contact_status !== 'accepted')
  const toggleInvite = (ref: string, place: 'list' | 'short') =>
    setInviting(inviting?.ref === ref && inviting.place === place ? null : { ref, place })
  const sent = () => {
    setInviting(null)
    void qc.invalidateQueries({ queryKey: ['selection', id] })
    void qc.invalidateQueries({ queryKey: ['quota', id] })
  }
  const renderCard = (c: CardData) => (
    <div key={c.ref} className="space-y-2">
      <CandidateCard card={c} onPin={onPin} needId={id}
        actions={canInvite(c) ? <Button size="sm" onClick={() => toggleInvite(c.ref, 'list')}>Пригласить</Button> : null} />
      {inviting?.ref === c.ref && inviting.place === 'list' && <InviteForm needId={id} cardRef={c.ref} onSent={sent} />}
    </div>
  )
  const short = sel.data?.shortlist ?? []
  const fit = sel.data?.fork_fit
  return (
    <Page>
      <PageHeader back={<BackLink to="/">Потребности</BackLink>} title={need.data?.title ?? 'Подборка'}
        actions={<>
          <Link to={`/employer/needs/${id}/invitations`} title="Квота: сколько приглашений можно отправить по этой потребности. Растёт с уровнем доверия компании." className="rounded-[10px] border border-line bg-white px-3 py-2 text-[13px] text-muted hover:border-line-strong">
            Приглашения{quota.data && <> · квота <b className="font-semibold text-ink">{quota.data.used} из {quota.data.limit}</b></>}
          </Link>
          <LinkButton to={`/employer/needs/${id}/edit`} variant="secondary" size="sm">Изменить</LinkButton>
          {need.data?.status === 'active' && (
            <Button variant="danger" size="sm" onClick={async () => {
              await closeNeed(id)
              await qc.invalidateQueries({ queryKey: ['needs'] })
              nav('/')
            }}>Закрыть потребность</Button>
          )}
        </>} />
      {((fit && fit.total > 0) || (sel.data?.diff && (sel.data.diff.added > 0 || sel.data.diff.removed.length > 0))) && (
        <div className="grid gap-3 md:grid-cols-2">
          {fit && fit.total > 0 && (
            <Card className="p-4 sm:px-[18px]">
              <p className="text-xs text-muted">Вилка в ожиданиях</p>
              <p className="mt-1 text-xl font-semibold"><span>у {fit.fit} из {fit.total}</span> <span className="text-[13px] font-normal text-muted">кандидатов, указавших ожидания</span></p>
              <p className="mt-1 text-xs text-muted">Сравниваем вилку потребности с ожиданиями кандидата.</p>
            </Card>
          )}
          {sel.data?.diff && (sel.data.diff.added > 0 || sel.data.diff.removed.length > 0) && <DiffCard diff={sel.data.diff} />}
        </div>
      )}
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-5">
          <div className="space-y-2.5">
            <div className="flex flex-wrap items-center gap-1.5">
              {need.data?.must.concat(need.data.nice).map((t) => <Chip key={t} active={!!f.techs?.includes(t)} onClick={() => setF({ ...f, techs: toggle(f.techs, t) })}>{t}</Chip>)}
              <Chip active={!!f.has_fsp} onClick={() => setF({ ...f, has_fsp: !f.has_fsp })}>есть достижения ФСП</Chip>
              {(Object.keys(FORMAT_TITLE) as Format[]).map((x) => <Chip key={x} active={!!f.formats?.includes(x)} onClick={() => setF({ ...f, formats: toggle(f.formats, x) })}>{FORMAT_TITLE[x]}</Chip>)}
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="mr-1 text-[13px] text-muted">Подтверждённые навыки:</span>
              {Object.entries(SKILL_TITLE).map(([code, title]) => <Chip key={code} active={!!f.skills?.includes(code)} onClick={() => setF({ ...f, skills: toggle(f.skills, code) })}>{title}</Chip>)}
            </div>
          </div>
          {sel.data?.blocks.map((b) => (
            <section key={b.block} className="space-y-3">
              <h2 className="flex items-center gap-2 text-[15px] font-semibold">{b.title}<span className="rounded-full bg-line px-2 py-px text-xs font-medium text-muted">{b.items.length}</span></h2>
              {b.items.map(renderCard)}
            </section>
          ))}
          {sel.data && sel.data.blocks.every((b) => b.items.length === 0) && sel.data.suggestions.length === 0 && (
            <Card><p>Под условия потребности пока никого нет. Попробуйте добавить соседний грейд или сократить обязательный стек.</p></Card>
          )}
          {sel.data && sel.data.suggestions.length > 0 && (
            <Card><p className="font-semibold">Никого не нашлось. Можно ослабить условия:</p>
              <ul className="mt-2 list-disc pl-5 text-sm">{sel.data.suggestions.map((s) => <li key={s.filter}>{s.label}: +{s.gain}</li>)}</ul></Card>
          )}
        </div>
        <aside aria-label="Шортлист" className="space-y-3 rounded-card bg-ink p-5 text-white lg:sticky lg:top-24">
          <div className="flex items-center justify-between">
            <h2 className="text-[15px] font-semibold">Шортлист</h2>
            <span className="font-mono text-[13px] text-night-muted">{short.length}</span>
          </div>
          {short.length === 0 && <p className="text-[13px] leading-normal text-night-muted">Закреплённые кандидаты остаются здесь при любых фильтрах.</p>}
          {short.map((c) => (
            <div key={c.ref} className="rounded-xl bg-night-3 px-3.5 py-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-mono text-[13px] font-semibold">{c.alias}</p>
                  <p className="mt-0.5 text-xs text-night-muted">
                    {GRADE_TITLE[c.grade]} · {c.grade_status === 'confirmed' ? 'подтверждён тестом' : 'не подтверждён'}
                    {c.contact_status ? ` · приглашение: ${STATUS_TITLE[c.contact_status]}` : ''}
                  </p>
                </div>
                <button type="button" aria-label={`Убрать ${c.alias} из шортлиста`} onClick={() => void onPin(c.ref, false)}
                  className="rounded px-1.5 text-base leading-none text-night-muted hover:text-white">×</button>
              </div>
              {canInvite(c) && <Button variant="light" size="sm" className="mt-2.5 w-full" onClick={() => toggleInvite(c.ref, 'short')}>Пригласить</Button>}
              {inviting?.ref === c.ref && inviting.place === 'short' && (
                <div className="mt-2.5 rounded-xl bg-white p-3 text-ink"><InviteForm needId={id} cardRef={c.ref} onSent={sent} /></div>
              )}
            </div>
          ))}
        </aside>
      </div>
    </Page>
  )
}
