import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError } from '../../api/client'
import { FORMAT_TITLE, type Format } from '../../api/employer'
import { getDetails, getMarket, getStack, openWindow, PROFILE_PDF_URL, saveDetails, saveStack, type Details, type ResumeDraft } from '../../api/profile'
import { FspSection } from '../../components/candidate/FspSection'
import MyCases from '../../components/candidate/MyCases'
import { ResumeImport } from '../../components/candidate/ResumeImport'
import { StackPicker } from '../../components/StackPicker'
import { Button, Card, ErrorText, Field, Input, Page, PageHeader, TechChip } from '../../components/ui'
import { buttonClass } from '../../components/ui-classes'

// Форма монтируется только после загрузки: начальное состояние берётся из props, без эффектов синхронизации
function DetailsForm({ initial }: { initial: Details }) {
  const qc = useQueryClient()
  const stack = useQuery({ queryKey: ['stack'], queryFn: getStack })
  const market = useQuery({ queryKey: ['market'], queryFn: getMarket })
  const [d, setD] = useState<Details>(initial)
  const [domains, setDomains] = useState(initial.domains.join(', '))
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [now] = useState(() => Date.now())  // момент открытия страницы; render остаётся чистым
  const set = <K extends keyof Details>(k: K, v: Details[K]) => { setSaved(false); setD({ ...d, [k]: v }) }
  // В выборе — всё, что кандидат заявил, включая уже подтверждённое: иначе сохранение стека его бы стёрло
  const declared = stack.data?.declared ?? []
  const save = async () => {
    setError(null)
    try {
      await saveDetails({ full_name: d.full_name, contacts: d.contacts, experience_years: d.experience_years, formats: d.formats,
        city: d.city, domains: d.domains, salary_threshold: d.salary_threshold, salary_gross_net: d.salary_gross_net })
    } catch (e) {
      setError(e instanceof ApiError ? `${e.title}${e.detail ? `: ${e.detail}` : ''}` : 'Не удалось сохранить')
      return
    }
    await qc.invalidateQueries({ queryKey: ['details'] })
    setSaved(true)
  }
  const openUntil = d.open_until ? new Date(d.open_until) : null
  // Черновик дополняет форму, а не затирает её: пустые поля заполняются, стек объединяется и сохраняется сразу
  const applyResume = async (r: ResumeDraft) => {
    setSaved(false)
    const nextDomains = d.domains.length ? d.domains : r.domains
    setD({ ...d, experience_years: d.experience_years ?? r.experience_years, city: d.city ?? r.city,
      formats: d.formats.length ? d.formats : r.formats, full_name: d.full_name ?? r.full_name,
      domains: nextDomains, contacts: { ...r.contacts, ...d.contacts } })
    setDomains(nextDomains.join(', '))
    if (r.stack.some((t) => !declared.includes(t))) {
      await saveStack([...new Set([...declared, ...r.stack])])
      await qc.invalidateQueries({ queryKey: ['stack'] })
    }
  }
  return (
    <Page narrow>
      <PageHeader title="Профиль и условия" actions={<a className={buttonClass('secondary', 'sm')} href={PROFILE_PDF_URL}>Скачать PDF-профиль</a>} />
      <ResumeImport onApply={applyResume} />
      <FspSection />
      <Card>
        <h2 className="text-lg font-semibold">Стек</h2>
        <div className="mt-3 flex flex-wrap gap-1.5">{(stack.data?.items ?? []).map((i) => (
          <TechChip key={i.tech} tech={i.tech} confirmed={i.state === 'confirmed'} declaredLabel />
        ))}</div>
        <p className="mt-2 text-sm text-muted">Галочкой отмечены технологии, подтверждённые тестом или навыком. В подборке они весят больше заявленных.</p>
        <div className="mt-3"><StackPicker label="Заявить технологии" value={declared} onChange={async (v) => {
          await saveStack(v)
          await qc.invalidateQueries({ queryKey: ['stack'] })
        }} /></div>
      </Card>
      <Card>
        <h2 className="text-lg font-semibold">Условия</h2>
        <div className="mt-3 space-y-3">
          <Field label="Минимальная зарплата (не видна работодателям)" htmlFor="thr"><Input id="thr" inputMode="numeric" value={d.salary_threshold ?? ''} onChange={(e) => set('salary_threshold', e.target.value ? Number(e.target.value.replace(/\D/g, '')) : null)} /></Field>
          {market.data?.median_net != null && <p className="text-sm text-muted">Для ориентира: медиана по вашей категории {market.data.median_net.toLocaleString('ru-RU')} ₽ на руки</p>}
          <div className="flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2"><input type="radio" checked={d.salary_gross_net === 'net'} onChange={() => set('salary_gross_net', 'net')} />на руки</label>
            <label className="flex items-center gap-2"><input type="radio" checked={d.salary_gross_net === 'gross'} onChange={() => set('salary_gross_net', 'gross')} />до вычета НДФЛ</label>
          </div>
          <fieldset className="flex flex-wrap gap-4 text-sm"><legend className="mb-1 text-[13px] font-medium text-ink-2">Формат</legend>{(Object.keys(FORMAT_TITLE) as Format[]).map((f) => (
            <label key={f} className="flex items-center gap-2"><input type="checkbox" checked={d.formats.includes(f)} onChange={() => set('formats', d.formats.includes(f) ? d.formats.filter((x) => x !== f) : [...d.formats, f])} />{FORMAT_TITLE[f]}</label>
          ))}</fieldset>
          <Field label="Город" htmlFor="city"><Input id="city" value={d.city ?? ''} onChange={(e) => set('city', e.target.value || null)} /></Field>
          <Field label="Сферы, в которых есть опыт (через запятую)" htmlFor="domains"><Input id="domains" placeholder="финтех, e-commerce" value={domains} onChange={(e) => {
            setDomains(e.target.value)
            set('domains', e.target.value.split(',').map((x) => x.trim()).filter(Boolean).slice(0, 10))
          }} /></Field>
          <Field label="Опыт, лет" htmlFor="exp"><Input id="exp" inputMode="decimal" value={d.experience_years ?? ''} onChange={(e) => set('experience_years', e.target.value ? Number(e.target.value.replace(',', '.')) : null)} /></Field>
        </div>
      </Card>
      <Card>
        <h2 className="text-lg font-semibold">ФИО и контакты</h2>
        <p className="text-sm text-muted">Компания увидит их после того, как вы примете её приглашение.</p>
        <div className="mt-3 space-y-3">
          <Field label="ФИО" htmlFor="fn"><Input id="fn" value={d.full_name ?? ''} onChange={(e) => set('full_name', e.target.value || null)} /></Field>
          <Field label="Telegram" htmlFor="tg"><Input id="tg" value={d.contacts.telegram ?? ''} onChange={(e) => set('contacts', { ...d.contacts, telegram: e.target.value })} /></Field>
          <Field label="Телефон" htmlFor="ph"><Input id="ph" value={d.contacts.phone ?? ''} onChange={(e) => set('contacts', { ...d.contacts, phone: e.target.value })} /></Field>
        </div>
      </Card>
      <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center gap-3 border-t border-line bg-white/95 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-card sm:border">
        <Button onClick={save}>Сохранить</Button>
        {saved && <span className="text-sm text-muted">Сохранено</span>}
        <ErrorText>{error}</ErrorText>
        <Button variant="secondary" onClick={async () => { const r = await openWindow(); setD({ ...d, open_until: r.open_until }) }}>
          {openUntil && openUntil.getTime() > now ? `Профиль открыт для предложений до ${openUntil.toLocaleDateString('ru-RU')} · продлить` : 'Открыть профиль для предложений'}
        </Button>
      </div>
      <MyCases />
    </Page>
  )
}

export default function ProfileDetailsPage() {
  const details = useQuery({ queryKey: ['details'], queryFn: getDetails })
  if (!details.data) return <Page narrow><p>Загрузка…</p></Page>
  return <DetailsForm initial={details.data} />
}
