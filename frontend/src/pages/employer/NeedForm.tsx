import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { GRADE_TITLE, type Grade, type Specialization } from '../../api/assessment'
import { ApiError } from '../../api/client'
import { createNeed, EMPLOYMENT_TITLE, FORMAT_TITLE, getNeed, updateNeed, type Employment, type Format, type NeedDraft, type NeedInput } from '../../api/employer'
import { NeedTextImport } from '../../components/employer/NeedTextImport'
import { StackPicker } from '../../components/StackPicker'
import { Button, Card, Field, Input } from '../../components/ui'

const SPECS: [Specialization, string][] = [['backend', 'Backend'], ['frontend', 'Frontend'], ['data', 'Data / Analytics']]

export function NeedFormView({ initial, onSubmit }: { initial?: NeedInput; onSubmit: (n: NeedInput) => void }) {
  const [n, setN] = useState<NeedInput>(initial ?? { title: '', specialization: 'backend', grades: [], must: [], nice: [], formats: [], city: null,
    salary_from: 0, salary_to: 0, gross_net: 'gross', contact_method: 'chat', employment: 'full' })
  const set = <K extends keyof NeedInput>(k: K, v: NeedInput[K]) => setN((x) => ({ ...x, [k]: v }))
  const toggle = <T,>(arr: T[], v: T) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v])
  const ready = n.title.trim() && n.grades.length && n.salary_from > 0 && n.salary_to >= n.salary_from
  return (
    <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); onSubmit(n) }}>
      <Field label="Название потребности" htmlFor="title"><Input id="title" value={n.title} onChange={(e) => set('title', e.target.value)} /></Field>
      <div className="flex flex-wrap gap-2">{SPECS.map(([c, t]) => (
        <button type="button" key={c} onClick={() => set('specialization', c)} className={`rounded-full px-4 py-1.5 text-sm font-semibold ${n.specialization === c ? 'bg-ink text-white' : 'bg-line-soft text-ink-2'}`}>{t}</button>
      ))}</div>
      <fieldset className="flex gap-4"><legend className="mb-1 text-sm font-medium text-ink">Целевые грейды</legend>
        {(['junior', 'middle', 'senior'] as Grade[]).map((g) => (
          <label key={g} className="flex gap-2"><input type="checkbox" checked={n.grades.includes(g)} onChange={() => set('grades', toggle(n.grades, g))} />{GRADE_TITLE[g]}</label>
        ))}
      </fieldset>
      <StackPicker label="Обязательный стек" value={n.must} onChange={(v) => set('must', v)} />
      <StackPicker label="Желательный стек" value={n.nice} onChange={(v) => set('nice', v)} />
      <fieldset className="flex gap-4"><legend className="mb-1 text-sm font-medium text-ink">Формат</legend>
        {(Object.keys(FORMAT_TITLE) as Format[]).map((f) => (
          <label key={f} className="flex gap-2"><input type="checkbox" checked={n.formats.includes(f)} onChange={() => set('formats', toggle(n.formats, f))} />{FORMAT_TITLE[f]}</label>
        ))}
      </fieldset>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Вилка от, ₽" htmlFor="from"><Input id="from" inputMode="numeric" value={n.salary_from || ''} onChange={(e) => set('salary_from', Number(e.target.value.replace(/\D/g, '')))} /></Field>
        <Field label="Вилка до, ₽" htmlFor="to"><Input id="to" inputMode="numeric" value={n.salary_to || ''} onChange={(e) => set('salary_to', Number(e.target.value.replace(/\D/g, '')))} /></Field>
        <fieldset className="flex items-end gap-3 pb-2 text-sm">
          <label className="flex gap-1"><input type="radio" checked={n.gross_net === 'gross'} onChange={() => set('gross_net', 'gross')} />до вычета НДФЛ</label>
          <label className="flex gap-1"><input type="radio" checked={n.gross_net === 'net'} onChange={() => set('gross_net', 'net')} />на руки</label>
        </fieldset>
      </div>
      <Field label="Занятость" htmlFor="employment">
        <select id="employment" aria-label="Занятость" className="w-full rounded-lg border border-line-strong px-3 py-2" value={n.employment ?? 'full'} onChange={(e) => set('employment', e.target.value as Employment)}>
          {(Object.keys(EMPLOYMENT_TITLE) as Employment[]).map((k) => <option key={k} value={k}>{EMPLOYMENT_TITLE[k]}</option>)}
        </select>
        <p className="mt-1 text-xs text-muted">Стажировку и каникулярную работу видят и кандидаты 14–17 лет с согласия законного представителя. Для полной занятости их не показываем.</p>
      </Field>
      <Field label="Город (если важен)" htmlFor="city"><Input id="city" value={n.city ?? ''} onChange={(e) => set('city', e.target.value || null)} /></Field>
      <Button type="submit" disabled={!ready}>Сохранить</Button>
    </form>
  )
}

function fromDraft(d: NeedDraft, text: string): NeedInput {
  return { title: d.title ?? '', specialization: d.specialization ?? 'backend', grades: d.grades, must: d.must, nice: d.nice,
    formats: d.formats, city: d.city ?? null, salary_from: d.salary_from ?? 0, salary_to: d.salary_to ?? 0,
    gross_net: d.gross_net ?? 'gross', contact_method: 'chat', employment: 'full', raw_text: text }
}

export default function NeedForm() {
  const { id } = useParams()
  const nav = useNavigate()
  const existing = useQuery({ queryKey: ['need', id], queryFn: () => getNeed(id!), enabled: !!id })
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState<{ n: NeedInput; info: NeedDraft; version: number } | null>(null)
  if (id && existing.isError) return <p role="alert" className="p-6 text-danger">{existing.error instanceof ApiError ? existing.error.title : 'Не удалось загрузить потребность'}</p>
  if (id && !existing.data) return <p className="p-6">Загрузка…</p>
  return (
    <div className="mx-auto max-w-3xl p-6"><Card>
      <h1 className="mb-4 text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">{id ? 'Потребность' : 'Новая потребность'}</h1>
      {error && <p className="mb-3 text-danger">{error}</p>}
      {!id && <NeedTextImport onDraft={(d, text) => setDraft({ n: fromDraft(d, text), info: d, version: (draft?.version ?? 0) + 1 })} />}
      {draft && (
        <div className="mb-4 rounded-lg border border-line-strong p-3 text-sm">
          <p>Заполнено {draft.info.source === 'llm' ? 'с помощью ИИ' : 'по словарю'}. Проверьте поля перед сохранением.</p>
          {draft.info.missing.length > 0 && <p className="text-danger">Не нашли в тексте: {draft.info.missing.join(', ')}</p>}
          {draft.info.unknown_terms.length > 0 && <p className="text-muted">Нет в словаре стека: {draft.info.unknown_terms.join(', ')}</p>}
        </div>
      )}
      <NeedFormView key={draft?.version ?? 0} initial={draft?.n ?? existing.data} onSubmit={async (n) => {
        try { const saved = id ? await updateNeed(id, n) : await createNeed(n); nav(`/employer/needs/${saved.id}`) }
        catch (e) { setError(e instanceof ApiError ? `${e.title}${e.detail ? `: ${e.detail}` : ''}` : 'Не удалось сохранить потребность') }
      }} />
    </Card></div>
  )
}
