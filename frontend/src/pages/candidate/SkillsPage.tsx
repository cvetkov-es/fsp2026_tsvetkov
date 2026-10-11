import { useQuery } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { resetCooldowns } from '../../api/assessment'
import { api, ApiError } from '../../api/client'
import { getSkills, startSkill, type Skill } from '../../api/skills'
import { Button, Card, ErrorText, LinkButton, Notice, Page, PageHeader, Pill, type PillTone } from '../../components/ui'

function statusText(s: Skill): string {
  if (s.status === 'passed') return 'подтверждён ✓'
  // дата нужна, только пока пересдача закрыта: прошедшая дата рядом с кнопкой старта сбивает с толку
  if (s.status === 'failed') return `не подтверждён${!s.available && s.available_at ? ` · пересдача с ${new Date(s.available_at).toLocaleDateString('ru-RU')}` : ''}`
  return 'не пройден'
}
const statusTone = (s: Skill): PillTone => (s.status === 'passed' ? 'success' : s.status === 'failed' ? 'danger' : 'neutral')
const pickDefault = (list: Skill[]) => (list.find((s) => s.recommended) ?? list[0])?.code ?? null

function SkillTile({ s, selected, onSelect }: { s: Skill; selected: boolean; onSelect: () => void }) {
  return (
    <button type="button" aria-pressed={selected} onClick={onSelect}
      className={`flex min-h-[150px] flex-col gap-3 rounded-2xl border-[1.5px] bg-white p-[18px] text-left transition ${selected ? 'border-primary' : 'border-line hover:border-primary-line'}`}>
      <span className="flex w-full items-center justify-between gap-2">
        <Pill tone={statusTone(s)}>{statusText(s)}</Pill>
        {s.recommended && <span className="text-xs font-semibold text-primary">Рекомендуем</span>}
      </span>
      <span className="text-lg font-semibold tracking-[-0.01em]">{s.title}</span>
      <span className="mt-auto text-[13px] leading-snug text-muted">{s.techs.join(' · ')}</span>
    </button>
  )
}

function SkillDetail({ s }: { s: Skill }) {
  const nav = useNavigate()
  const [rules, setRules] = useState(false)
  const [pledge, setPledge] = useState(false)
  const [extra, setExtra] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const ai = s.format === 'ai'
  const canStart = !s.active_attempt_id && s.available && s.bank_ready
  const start = async () => {
    setError(null)
    setBusy(true)
    try { const a = await startSkill(s.code, { accept_rules: rules, pledge, extra_time: extra }); nav(`/test/${a.id}`) }
    catch (e) { setError(e instanceof ApiError ? e.title : 'Не удалось начать тест') } finally { setBusy(false) }
  }
  return (
    <Card as="aside" className="space-y-[18px] lg:sticky lg:top-24">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[13px] text-muted">{ai ? 'Отдельный формат · ИИ разрешён' : '6 заданий · без ИИ и поиска'}</span>
        <Pill tone={statusTone(s)}>Статус: {statusText(s)}</Pill>
      </div>
      <h2 className="text-[26px] font-semibold tracking-[-0.02em]">{s.title}</h2>
      <p className="text-[15px] leading-relaxed text-ink-2">{s.summary}</p>
      {ai && <p className="text-sm">{s.items} готовых решений за {s.minutes} минут. Для каждого решите: верно, есть ошибка (укажите строку и вход, на котором ломается) или требование нужно уточнить. Пользоваться ИИ можно.</p>}
      <p className="text-[13px] text-muted">Подтверждает в профиле: {s.techs.join(', ')}</p>
      {s.active_attempt_id && <LinkButton to={`/test/${s.active_attempt_id}`}>Продолжить начатый тест</LinkButton>}
      {canStart && (
        <div className="space-y-2.5 border-t border-line-soft pt-[18px] text-sm leading-snug">
          <label className="flex gap-2.5"><input type="checkbox" className="mt-0.5" checked={rules} onChange={(e) => setRules(e.target.checked)} />{ai
            ? `Принимаю правила: ${s.items} решений за ${s.minutes} минут, ИИ разрешён, пересдача через 14 дней`
            : 'Принимаю правила: 6 заданий, без ИИ и поиска, пересдача через 14 дней'}</label>
          <label className="flex gap-2.5"><input type="checkbox" className="mt-0.5" checked={pledge} onChange={(e) => setPledge(e.target.checked)} />{ai ? 'Обязуюсь проходить без помощи других людей' : 'Обязуюсь проходить без посторонней помощи'}</label>
          <label className="flex gap-2.5 text-muted"><input type="checkbox" className="mt-0.5" checked={extra} onChange={(e) => setExtra(e.target.checked)} />Нужно больше времени (+50%)</label>
          <Button size="lg" className="mt-1.5 w-full" disabled={!rules || !pledge || busy} onClick={() => void start()}>
            {ai ? `Пройти · ${s.items} решений за ${s.minutes} минут` : 'Пройти · 6 заданий'}
          </Button>
          <ErrorText>{error}</ErrorText>
        </div>
      )}
      {!s.bank_ready && <Notice>Тест навыка готовится.</Notice>}
      {s.status === 'passed' && <Notice tone="success">Технологии навыка отмечены ✓ в профиле и в подборке.</Notice>}
    </Card>
  )
}

/** Навыки (процесс 2.5, 04-skills.png): короткий тест подтверждает технологии стека; на грейд не влияет. */
export default function SkillsPage() {
  const q = useQuery({ queryKey: ['skills'], queryFn: getSkills })
  // Тот же запрос, что в шапке: отвечает только в демо-режиме. Навыки доступны и до опроса, поэтому сброс — и здесь
  const demo = useQuery({ queryKey: ['personas'], queryFn: () => api<unknown[]>('/demo/personas'), retry: false })
  const [error, setError] = useState<string | null>(null)
  const [picked, setPicked] = useState<string | null>(null)
  const detail = useRef<HTMLDivElement>(null)
  const list = q.data ?? []
  const current = list.find((s) => s.code === (picked ?? pickDefault(list))) ?? null
  const select = (code: string) => {
    setPicked(code)
    // На узком экране карточка навыка — под сеткой: прокручиваем к ней
    if (window.matchMedia?.('(max-width: 1023px)').matches) detail.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }
  return (
    <Page>
      <PageHeader title="Навыки"
        description="Шесть заданий подтверждают технологии из вашего стека, и работодатель увидит их с галочкой. На грейд навыки не влияют."
        actions={demo.isSuccess && (
          <Button variant="ghost" size="sm" onClick={async () => {
            setError(null)
            try { await resetCooldowns(); await q.refetch() } catch (e) { setError(e instanceof ApiError ? e.title : 'Не удалось выполнить действие') }
          }}>Разрешить пересдачу сейчас (демо)</Button>
        )} />
      <ErrorText>{error}</ErrorText>
      {q.isPending && <p>Загрузка…</p>}
      <ErrorText>{q.isError ? (q.error instanceof ApiError ? q.error.title : 'Не удалось загрузить навыки') : null}</ErrorText>
      {current && (
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,440px)]">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {list.map((s) => <SkillTile key={s.code} s={s} selected={s.code === current.code} onSelect={() => select(s.code)} />)}
          </div>
          <div ref={detail} className="scroll-mt-24"><SkillDetail key={current.code} s={current} /></div>
        </div>
      )}
    </Page>
  )
}
