import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCompany, saveCompany } from '../../api/employer'
import { errorText } from '../../api/errors'
import { requestL3, verifyDomain, verifyInn } from '../../api/trust'
import IntegrationsBlock from '../../components/employer/IntegrationsBlock'
import { Button, Card, Field, Input } from '../../components/ui'

const LEVELS = ['L0', 'L1', 'L2', 'L3']
const reached = (current: string, need: string) => LEVELS.indexOf(current) >= LEVELS.indexOf(need)

/** Уровни доверия (процесс 4.1): L1 — домен почты, L2: юрлицо по ИНН, L3 — решение модератора. */
function TrustBlock({ company, onChanged }: { company: NonNullable<ReturnType<typeof useCompany>['data']>; onChanged: () => Promise<unknown> }) {
  const [inn, setInn] = useState('')
  const [comment, setComment] = useState('')
  const [error, setError] = useState<string | null>(null)
  const lvl = company.trust_level
  const run = async (f: () => Promise<unknown>) => {
    setError(null)
    try { await f(); await onChanged() } catch (e) { setError(errorText(e)) }
  }
  return (
    <div className="mt-6 space-y-3 border-t border-line pt-4">
      <h2 className="text-lg font-semibold">{`Уровень доверия: ${lvl}`}</h2>
      <p className="text-sm text-muted">От уровня зависят квота приглашений, число потребностей, вес ваших оценок кандидатов, задачи и помощник к собеседованию.</p>
      <p className="text-sm text-muted">L0: подтверждена только почта. L1: корпоративный домен. L2: юрлицо по ИНН. L3: проверка модератором.</p>
      {company.legal_name && <p className="text-sm">Юрлицо: <span className="font-semibold">{company.legal_name}</span></p>}
      <div className="space-y-1">
        <p className="text-sm font-semibold">L1: корпоративный домен</p>
        <Button type="button" disabled={reached(lvl, 'L1')} onClick={() => run(verifyDomain)}>Подтвердить корпоративный домен</Button>
        {company.domain && <p className="text-xs text-muted">{`Домен: ${company.domain}`}</p>}
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold">L2: юрлицо по ИНН</p>
        <div className="flex flex-wrap items-center gap-2">
          <div className="w-48"><Input aria-label="ИНН" inputMode="numeric" maxLength={12} disabled={!reached(lvl, 'L1') || reached(lvl, 'L2')}
            value={inn} onChange={(e) => setInn(e.target.value.replace(/\D/g, ''))} /></div>
          <Button type="button" disabled={!reached(lvl, 'L1') || reached(lvl, 'L2') || inn.length < 10} onClick={() => run(() => verifyInn(inn))}>Проверить юрлицо</Button>
        </div>
        {!reached(lvl, 'L1') && <p className="text-xs text-muted">Сначала подтвердите корпоративный домен на уровне L1.</p>}
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold">L3: заявка модератору</p>
        {lvl === 'L3' ? <p className="text-sm">Присвоен высший уровень L3.</p> : company.l3_pending ? <p className="text-sm">Заявка на L3 на рассмотрении. Ответ придёт в уведомлениях.</p> : (
          <div className="flex flex-wrap items-center gap-2">
            <Input aria-label="Комментарий к заявке на L3" maxLength={1000} disabled={lvl !== 'L2'} value={comment} onChange={(e) => setComment(e.target.value)} />
            <Button type="button" disabled={lvl !== 'L2'} onClick={() => run(() => requestL3(comment))}>Отправить заявку на L3</Button>
          </div>
        )}
      </div>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
    </div>
  )
}

const useCompany = () => useQuery({ queryKey: ['company'], queryFn: getCompany })

export default function CompanyForm() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const q = useCompany()
  const [name, setName] = useState<string | null>(null)
  const [description, setDescription] = useState<string | null>(null)
  const [industry, setIndustry] = useState<string | null>(null)
  const [site, setSite] = useState<string | null>(null)
  const c = q.data
  const v = { name: name ?? c?.name ?? '', description: description ?? c?.description ?? '', industry: industry ?? c?.industry ?? '', site: site ?? c?.contacts?.site ?? '' }
  return (
    <div className="mx-auto max-w-2xl p-6"><Card>
      <h1 className="mb-4 text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">Профиль компании</h1>
      <div className="space-y-3">
        <Field label="Название" htmlFor="cname"><Input id="cname" value={v.name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="Направление деятельности" htmlFor="ind"><Input id="ind" value={v.industry} onChange={(e) => setIndustry(e.target.value)} /></Field>
        <Field label="Чем занимается команда" htmlFor="desc"><textarea id="desc" className="w-full rounded-lg border border-line-strong p-3" rows={4} value={v.description} onChange={(e) => setDescription(e.target.value)} /></Field>
        <Field label="Сайт или контакт" htmlFor="site"><Input id="site" value={v.site} onChange={(e) => setSite(e.target.value)} /></Field>
        <Button disabled={!v.name.trim()} onClick={async () => {
          await saveCompany({ name: v.name, description: v.description || null, industry: v.industry || null, contacts: v.site ? { site: v.site } : {} })
          await qc.invalidateQueries({ queryKey: ['company'] })
          nav('/')
        }}>Сохранить</Button>
      </div>
      {c && <TrustBlock company={c} onChanged={() => qc.invalidateQueries({ queryKey: ['company'] })} />}
      {c && <IntegrationsBlock />}
    </Card></div>
  )
}
