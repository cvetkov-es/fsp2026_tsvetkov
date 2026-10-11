import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { AuthShell, AuthTabs } from '../components/AuthShell'
import { Button, ErrorText, Field, Input, Notice, Segmented } from '../components/ui'
import { linkClass } from '../components/ui-classes'

export type RegisterPayload = {
  email: string; password: string; role: 'candidate' | 'employer'; birth_date: string | null
  consents: { processing: boolean; distribution_preset: 'standard' | 'minimal' | null }
}

export type ConsentText = { type: string; version: string; title: string; body: string }

export function ConsentBody({ text }: { text?: ConsentText }) {
  if (!text) return null
  return (
    <details className="ml-6 text-xs text-muted">
      <summary className={`cursor-pointer ${linkClass}`}>Текст согласия</summary>
      <p className="mt-1 whitespace-pre-line">{text.body}</p>
    </details>
  )
}

export function RegisterForm({ onSubmit, texts = [] }: { onSubmit: (p: RegisterPayload) => void; texts?: ConsentText[] }) {
  const textOf = (type: string) => texts.find((t) => t.type === type)
  const [role, setRole] = useState<'candidate' | 'employer'>('candidate')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [birthDate, setBirthDate] = useState('')
  const [processing, setProcessing] = useState(false)
  const [preset, setPreset] = useState<'standard' | 'minimal' | null>(null)
  const isCandidate = role === 'candidate'
  const ready = email && password.length >= 8 && processing && (!isCandidate || (preset && birthDate))

  return (
    <form
      className="flex flex-col gap-3.5"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit({ email, password, role, birth_date: isCandidate ? birthDate : null,
          consents: { processing, distribution_preset: isCandidate ? preset : null } })
      }}
    >
      <Segmented label="Кто вы" value={role} onChange={setRole}
        options={[{ value: 'candidate', label: 'Я ищу работу' }, { value: 'employer', label: 'Я работодатель' }]} />
      <Field label="Email" htmlFor="email"><Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
      <Field label="Пароль (от 8 символов)" htmlFor="password"><Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
      {isCandidate && (
        <Field label="Дата рождения (храним только год)" htmlFor="birth"><Input id="birth" type="date" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} /></Field>
      )}
      <label className="flex items-start gap-2.5 text-sm leading-snug">
        <input type="checkbox" checked={processing} onChange={(e) => setProcessing(e.target.checked)} />
        <span>Даю согласие на обработку персональных данных</span>
      </label>
      <ConsentBody text={textOf('processing')} />
      {isCandidate && (
        <fieldset className="flex flex-col gap-2 text-sm">
          <legend className="mb-1 text-[13px] font-medium text-ink-2">Что увидят работодатели (ФИО и контакты скрыты)</legend>
          <label className="flex items-start gap-2.5 leading-snug"><input type="radio" name="preset" checked={preset === 'standard'} onChange={() => setPreset('standard')} />Стандартная видимость (рекомендуем)</label>
          <label className="flex items-start gap-2.5 leading-snug"><input type="radio" name="preset" checked={preset === 'minimal'} onChange={() => setPreset('minimal')} />Минимальная видимость</label>
          <ConsentBody text={textOf('distribution')} />
        </fieldset>
      )}
      <Button type="submit" size="lg" className="mt-1 w-full" disabled={!ready}>Зарегистрироваться</Button>
    </form>
  )
}

export default function RegisterPage() {
  const texts = useQuery({
    queryKey: ['consent-texts'],
    queryFn: async () => (await api<{ texts: ConsentText[] }>('/consents/texts')).texts,
  })
  const [verifyUrl, setVerifyUrl] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return (
    <AuthShell>
      <AuthTabs active="register" />
      <h2 className="mb-6 text-[28px] font-semibold tracking-[-0.02em]">Создать аккаунт</h2>
      {done ? (
        <div className="space-y-3">
          <p>Мы отправили письмо со ссылкой для подтверждения почты.</p>
          {verifyUrl && <Notice tone="info">Демо-режим: <a className={linkClass} href={verifyUrl}>подтвердить почту</a></Notice>}
          <Link className={linkClass} to="/login">Ко входу</Link>
        </div>
      ) : (
        <>
          <ErrorText className="mb-3">{error}</ErrorText>
          <RegisterForm texts={texts.data} onSubmit={async (p) => {
            try {
              const r = await api<{ verify_url: string | null }>('/auth/register', { method: 'POST', body: p })
              setVerifyUrl(r.verify_url); setDone(true)
            } catch (e) { setError(e instanceof ApiError ? e.title : 'Не удалось зарегистрироваться. Попробуйте ещё раз') }
          }} />
        </>
      )}
    </AuthShell>
  )
}
