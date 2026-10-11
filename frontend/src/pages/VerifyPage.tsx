import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { Card, ErrorText, Page } from '../components/ui'
import { linkClass } from '../components/ui-classes'

export default function VerifyPage() {
  const [params] = useSearchParams()
  const [state, setState] = useState<'pending' | 'ok' | 'error'>('pending')
  const [msg, setMsg] = useState('')
  // Токен одноразовый: StrictMode и повторный рендер не должны отправить его второй раз
  const sentToken = useRef<string | null>(null)
  useEffect(() => {
    const token = params.get('token') ?? ''
    if (sentToken.current === token) return
    sentToken.current = token
    api('/auth/verify', { method: 'POST', body: { token } })
      .then(() => setState('ok'))
      .catch((e) => { setState('error'); setMsg(e instanceof ApiError ? e.title : 'Не удалось подтвердить почту') })
  }, [params])
  return (
    <Page narrow>
      <Card>
        {state === 'pending' && <p>Проверяем ссылку…</p>}
        {state === 'ok' && <p>Почта подтверждена. <Link className={linkClass} to="/login">Войти</Link></p>}
        <ErrorText>{state === 'error' ? msg : null}</ErrorText>
      </Card>
    </Page>
  )
}
