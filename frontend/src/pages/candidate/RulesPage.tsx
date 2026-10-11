import { useQuery } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { getProfile, GRADE_TITLE, startAttempt, type Grade } from '../../api/assessment'
import { api, ApiError } from '../../api/client'
import { Button, Card, ErrorText, Notice, Page, PageHeader } from '../../components/ui'
import { linkClass } from '../../components/ui-classes'

type Texts = { texts: { type: string; title: string; body: string }[] }

export default function RulesPage() {
  const [params] = useSearchParams()
  const nav = useNavigate()
  const grade = (params.get('grade') ?? 'middle') as Grade
  const express = params.get('express') === '1'
  const texts = useQuery({ queryKey: ['consent-texts'], queryFn: () => api<Texts>('/consents/texts') })
  const rules = texts.data?.texts.find((t) => t.type === 'automated_rules')
  const [accept, setAccept] = useState(false)
  const [pledge, setPledge] = useState(false)
  const [extra, setExtra] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const pending = useRef(false)
  const profile = useQuery({ queryKey: ['profile'], queryFn: getProfile })
  const retest = profile.data?.grade_status === 'confirmed' && profile.data.confirmed_grade === grade
  const start = async () => {
    if (pending.current) return // двойной клик не создаёт второй запрос
    pending.current = true
    setBusy(true)
    setError(null)
    try {
      const a = await startAttempt({ target_grade: grade, express, extra_time: extra, accept_rules: accept, pledge })
      nav(`/test/${a.id}`)
    } catch (e) {
      setError(e instanceof ApiError
        ? `${e.title}${e.code === 'cooldown' && e.detail ? ` (до ${new Date(e.detail).toLocaleDateString('ru-RU')})` : ''}`
        : 'Не удалось связаться с сервером')
    } finally { pending.current = false; setBusy(false) }
  }
  return (
    <Page narrow>
      <PageHeader eyebrow="Правила теста" title={`Тест на ${GRADE_TITLE[grade]}`}
        description={express ? 'Экспресс · 3–5 минут' : 'Полный тест: число заданий зависит от ваших ответов'} />
      <Card className="space-y-5">
        {retest && <Notice tone="info">{GRADE_TITLE[grade]} у вас уже подтверждён. Новая попытка заменит текущий результат.</Notice>}
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl bg-success-tint p-4"><p className="font-semibold text-success">Можно</p><p className="mt-1 text-sm">Бумага и ручка.</p></div>
          <div className="rounded-xl bg-danger-soft p-4"><p className="font-semibold text-danger">Нельзя</p><p className="mt-1 text-sm">ИИ, поиск, запуск кода, помощь других людей.</p></div>
        </div>
        <p className="text-sm leading-relaxed text-ink-2">Мы видим, если вы уходите со вкладки или вставляете текст. Тест за это не прерывается. <Link className={linkClass} to="/about/threat-model">Модель угроз</Link></p>
        {rules && <details className="text-sm"><summary className={`cursor-pointer ${linkClass}`}>{rules.title}</summary><p className="mt-2 whitespace-pre-wrap">{rules.body}</p></details>}
        <div className="space-y-2.5 border-t border-line-soft pt-5 text-sm">
          <label className="flex gap-2.5"><input type="checkbox" className="mt-0.5" checked={accept} onChange={(e) => setAccept(e.target.checked)} />Согласен с автоматическими правилами платформы</label>
          <label className="flex gap-2.5"><input type="checkbox" className="mt-0.5" checked={pledge} onChange={(e) => setPledge(e.target.checked)} />Обязуюсь проходить тест самостоятельно</label>
          <label className="flex gap-2.5 text-muted"><input type="checkbox" className="mt-0.5" checked={extra} onChange={(e) => setExtra(e.target.checked)} />Нужно больше времени (+50%, без объяснения причин)</label>
        </div>
        <ErrorText>{error}</ErrorText>
        <Button size="lg" disabled={!accept || !pledge || busy} onClick={start}>Начать</Button>
      </Card>
    </Page>
  )
}
