import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { FSP_LOGIN_URL, fspErrorText } from '../api/fsp'
import { useAuth } from '../auth/AuthContext'
import { AuthShell, AuthTabs } from '../components/AuthShell'
import { Button, ErrorText, Field, Input } from '../components/ui'
import { buttonClass } from '../components/ui-classes'

export default function LoginPage() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [params] = useSearchParams()
  const fspError = fspErrorText(params.get('fsp_error'))
  return (
    <AuthShell>
      <AuthTabs active="login" />
      <h2 className="mb-6 text-[28px] font-semibold tracking-[-0.02em]">С возвращением</h2>
      <ErrorText className="mb-3">{fspError}</ErrorText>
      <a href={FSP_LOGIN_URL} className={`${buttonClass('primary', 'lg')} w-full`}>
        <span aria-hidden="true" className="grid size-5 place-items-center rounded-[5px] bg-white text-[8px] font-bold text-primary">ID</span>
        Войти через FSP ID
      </a>
      <p className="mt-2.5 text-center text-[13px] text-muted">Достижения ФСП появятся в профиле сами</p>
      <div className="my-7 flex items-center gap-3 text-[13px] text-subtle">
        <span className="h-px flex-1 bg-line" />или по почте<span className="h-px flex-1 bg-line" />
      </div>
      <form className="flex flex-col gap-3.5" onSubmit={async (e) => {
        e.preventDefault()
        setError(null)
        setBusy(true)
        try { await login(email, password); nav('/') } catch (err) { setError(err instanceof ApiError ? err.title : 'Не удалось войти. Попробуйте ещё раз') } finally { setBusy(false) }
      }}>
        <Field label="Email" htmlFor="email"><Input id="email" type="email" autoComplete="email" placeholder="you@example.ru" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Пароль" htmlFor="password"><Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        <ErrorText>{error}</ErrorText>
        <Button type="submit" variant="secondary" size="lg" disabled={busy} className="mt-1">Войти</Button>
      </form>
    </AuthShell>
  )
}
