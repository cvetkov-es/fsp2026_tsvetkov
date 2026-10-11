import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { completeFsp, getFspPending } from '../api/fsp'
import { useAuth } from '../auth/AuthContext'
import { AuthShell } from '../components/AuthShell'
import { Button, ErrorText, Field, Input, Notice } from '../components/ui'
import { ConsentBody, type ConsentText } from './RegisterPage'

/** FSP ID подтвердил человека, аккаунта нет: согласия №1–2 и дата рождения — как в обычной регистрации. */
export default function FspFinishPage() {
  const [params] = useSearchParams()
  const ticket = params.get('ticket') ?? ''
  const nav = useNavigate()
  const { refresh } = useAuth()
  const pending = useQuery({ queryKey: ['fsp-pending', ticket], queryFn: () => getFspPending(ticket), retry: false, enabled: !!ticket })
  const texts = useQuery({ queryKey: ['consent-texts'], queryFn: async () => (await api<{ texts: ConsentText[] }>('/consents/texts')).texts })
  const [birthDate, setBirthDate] = useState('')
  const [processing, setProcessing] = useState(false)
  const [preset, setPreset] = useState<'standard' | 'minimal' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const textOf = (type: string) => texts.data?.find((t) => t.type === type)
  if (!ticket || pending.isError) {
    const why = pending.error instanceof ApiError ? pending.error.title : 'Ссылка устарела. Начните вход через FSP ID заново.'
    return <AuthShell><Notice tone="danger">{why}</Notice></AuthShell>
  }
  if (!pending.data) return <AuthShell><p>Загрузка…</p></AuthShell>
  return (
    <AuthShell>
      <h2 className="mb-2 text-[28px] font-semibold tracking-[-0.02em]">Аккаунт через FSP ID</h2>
      <p className="mb-4 text-sm text-muted">{pending.data.name} · {pending.data.email}. Почта подтверждена через FSP ID. Осталось дать согласия и указать дату рождения.</p>
      <ErrorText className="mb-3">{error}</ErrorText>
      <form className="flex flex-col gap-3.5" onSubmit={async (e) => {
        e.preventDefault()
        setError(null)
        try {
          await completeFsp({ ticket, birth_date: birthDate, consents: { processing, distribution_preset: preset } })
          await refresh()
          nav('/candidate/profile')
        } catch (err) { setError(err instanceof ApiError ? `${err.title}${err.detail ? `: ${err.detail}` : ''}` : 'Не удалось создать аккаунт. Попробуйте ещё раз') }
      }}>
        <Field label="Дата рождения (храним только год)" htmlFor="birth"><Input id="birth" type="date" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} /></Field>
        <label className="flex items-start gap-2.5 text-sm leading-snug"><input type="checkbox" checked={processing} onChange={(e) => setProcessing(e.target.checked)} /><span>Даю согласие на обработку персональных данных</span></label>
        <ConsentBody text={textOf('processing')} />
        <fieldset className="flex flex-col gap-2 text-sm">
          <legend className="mb-1 text-[13px] font-medium text-ink-2">Что увидят работодатели (ФИО и контакты скрыты)</legend>
          <label className="flex items-start gap-2.5 leading-snug"><input type="radio" name="preset" checked={preset === 'standard'} onChange={() => setPreset('standard')} />Стандартная видимость (рекомендуем)</label>
          <label className="flex items-start gap-2.5 leading-snug"><input type="radio" name="preset" checked={preset === 'minimal'} onChange={() => setPreset('minimal')} />Минимальная видимость: без города и достижений ФСП</label>
          <ConsentBody text={textOf('distribution')} />
        </fieldset>
        <Button type="submit" size="lg" className="w-full" disabled={!birthDate || !processing || !preset}>Создать аккаунт</Button>
      </form>
    </AuthShell>
  )
}
