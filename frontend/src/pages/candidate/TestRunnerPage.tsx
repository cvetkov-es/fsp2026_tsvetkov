import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { extendAttempt, getAttempt, GRADE_TITLE, nextItem, submitAnswer, type AttemptState, type Grade } from '../../api/assessment'
import { ApiError } from '../../api/client'
import { SKILL_TITLE } from '../../api/employer'
import { AnswerInput } from '../../components/test/AnswerInput'
import { copyGuard } from '../../components/test/copy-guard'
import { PromptCode, PromptHint, PromptTables, PromptText } from '../../components/test/ItemPrompt'
import ReportItem from '../../components/test/ReportItem'
import { Timer } from '../../components/test/Timer'
import { useFocusMode } from '../../components/focus-mode'
import { verdictReady } from '../../components/test/verdict'
import { Button, Card, ErrorText, LinkButton, Notice } from '../../components/ui'
import { useIntegrity } from '../../hooks/useIntegrity'
import ResultView from './ResultView'

const message = (e: unknown) => (e instanceof ApiError ? e.title : 'Не удалось связаться с сервером')

function attemptTitle(s: AttemptState): string {
  if (s.target_grade === 'skill') return s.skill_code === 'ai' ? 'Работа с ИИ' : `Навык «${SKILL_TITLE[s.skill_code ?? ''] ?? s.skill_code ?? ''}»`
  return `Тест на ${GRADE_TITLE[s.target_grade]} · ${s.express ? 'экспресс' : 'полный тест'}`
}

// Число заданий известно у «Работы с ИИ» и во второй фазе; в первой фазе адаптивный тест сам решает, когда остановиться
function progressOf(s: AttemptState): { done: number; total: number | null } {
  if (s.skill_code === 'ai') return { done: s.n_answered, total: s.ai?.total ?? null }
  if (s.stage === 'phase2' || s.stage === 'transition') return { done: s.phase2_answered, total: s.phase2_total }
  return { done: s.n_answered, total: null }
}

function Progress({ done, total }: { done: number; total: number | null }) {
  const n = Math.max(total ?? done + 1, 1)
  // Длина известна — деления делят полосу; неизвестна — деления фиксированной ширины растут слева, без «остатка»
  const size = total === null ? 'min-w-0 max-w-6 flex-1' : 'min-w-0 flex-1'
  return (
    <div role="progressbar" aria-label="Пройдено заданий" aria-valuemin={0} aria-valuenow={total === null ? undefined : done} aria-valuemax={total ?? undefined}
      aria-valuetext={total === null ? `Пройдено заданий: ${done}` : undefined}
      className="order-last flex w-full gap-1 sm:order-none sm:mx-auto sm:max-w-[420px] sm:flex-1">
      {Array.from({ length: n }, (_, i) => <span key={i} className={`h-1 rounded-sm ${size} ${i < done ? 'bg-primary' : i === done ? 'bg-primary-mist' : 'bg-line'}`} />)}
    </div>
  )
}

/** Фокус-режим (02-test.png): попытка закрывает шапку сайта. Выход в кабинет — только между заданиями: таймер открытого задания идёт на сервере. */
function FocusShell({ state, canLeave, timer, children }: { state: AttemptState; canLeave: boolean; timer?: ReactNode; children: ReactNode }) {
  const p = progressOf(state)
  useFocusMode(true)  // шапка сайта под оболочкой недоступна и с клавиатуры
  return (
    <div data-testid="focus-shell" className="fixed inset-0 z-30 overflow-y-auto bg-white">
      <div className="border-b border-line">
        <div className="mx-auto flex min-h-16 max-w-[1240px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          {canLeave && <LinkButton to="/" variant="secondary" size="sm">← В кабинет</LinkButton>}
          <p className="text-sm font-medium">{attemptTitle(state)}</p>
          <Progress done={p.done} total={p.total} />
          {timer && <div className="ml-auto sm:ml-0">{timer}</div>}
        </div>
      </div>
      <div className="mx-auto max-w-[1240px] px-4 pb-16 pt-10 sm:px-6">{children}</div>
    </div>
  )
}

function Pause({ children }: { children: ReactNode }) {
  return <div className="mx-auto max-w-xl"><Card className="space-y-4">{children}</Card></div>
}

export default function TestRunnerPage() {
  const { attemptId = '' } = useParams()
  const nav = useNavigate()
  const integrity = useIntegrity()
  const [state, setState] = useState<AttemptState | null>(null)
  const [value, setValue] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const pending = useRef(false)

  const show = useCallback((s: AttemptState) => { setValue(null); setState(s) }, [])

  // Одно действие за раз: двойной клик и таймер не отправляют второй запрос
  const run = useCallback(async (fn: () => Promise<void>) => {
    if (pending.current) return
    pending.current = true
    setBusy(true)
    setError(null)
    try { await fn() } catch (e) { setError(message(e)) } finally { pending.current = false; setBusy(false) }
  }, [])

  useEffect(() => {
    getAttempt(attemptId)
      .then(async (s) => {
        // Первое задание открывается сразу после «Начать»; дальше — только по кнопке (пауза без ограничений).
        // «Работа с ИИ» идёт без пауз: общий таймер, поэтому открытый вердикт открывается и после перезагрузки
        if ((s.stage === 'phase1' || s.stage === 'phase2') && !s.item && (s.n_answered === 0 || s.skill_code === 'ai')) s = await nextItem(s.id)
        show(s)
      })
      .catch((e) => setLoadError(message(e)))
  }, [attemptId, show])

  const openNext = () => run(async () => { if (state) show(await nextItem(state.id)) })

  const submit = useCallback(() => run(async () => {
    if (!state?.item) return
    const events = integrity.take()
    let s: AttemptState
    try { s = await submitAnswer(state.id, state.item.seq, value, events) } catch (e) {
      integrity.restore(events)
      // Таймер истёк, пока вкладка была в фоне (браузер замедляет таймеры): сервер уже закрыл попытку — показываем итог
      if (e instanceof ApiError && e.code === 'attempt_closed') { show(await getAttempt(state.id)); return }
      throw e
    }
    show(s.skill_code === 'ai' && s.stage === 'phase1' && !s.item ? await nextItem(s.id) : s)
  }), [run, state, value, integrity, show])

  if (loadError) return <div className="p-6"><ErrorText>{loadError}</ErrorText></div>
  if (!state) return <p className="p-6">Загрузка…</p>
  if (state.stage === 'finished') return <ResultView state={state} />
  if (state.stage === 'incomplete') {
    return (
      <FocusShell state={state} canLeave>
        <Pause>
          {state.bank_exhausted
            ? <p>Заданий не хватило, чтобы принять решение. Попытка не засчитана, пересдать можно сразу.</p>
            : <p>Попытка закрыта до конца теста. Она не засчитана, пересдать можно сразу.</p>}
        </Pause>
      </FocusShell>
    )
  }
  if (state.stage === 'transition') {
    const n = state.phase2_total - state.phase2_answered
    return (
      <FocusShell state={state} canLeave>
        <Pause>
          <h1 className="text-2xl font-semibold tracking-[-0.02em]">{GRADE_TITLE[state.target_grade as Grade]}: грейд подтверждён</h1>
          <p>Ещё {n} {n === 1 ? 'задание' : n < 5 ? 'задания' : 'заданий'} уточнят вашу позицию в категории и могут открыть тест на грейд выше.</p>
          <div className="flex flex-wrap items-center gap-3">
            <Button disabled={busy} onClick={openNext}>Продолжить</Button>
            <Button variant="ghost" onClick={() => nav('/')}>Позже</Button>
          </div>
          <ErrorText>{error}</ErrorText>
        </Pause>
      </FocusShell>
    )
  }
  if (state.stage === 'awaiting_continue') {
    return (
      <FocusShell state={state} canLeave>
        <Pause>
          <h1 className="text-xl font-semibold">Результат пока неоднозначен</h1>
          <p>Экспресс-теста не хватило для точного результата. Продолжите эту же попытку, осталось несколько заданий. Вернуться к ней можно в течение 72 часов.</p>
          <div className="flex flex-wrap items-center gap-3">
            <Button disabled={busy} onClick={() => run(async () => { const s = await extendAttempt(state.id); show(await nextItem(s.id)) })}>Продолжить тест</Button>
            <LinkButton to="/" variant="ghost">Позже</LinkButton>
          </div>
          <ErrorText>{error}</ErrorText>
        </Pause>
      </FocusShell>
    )
  }
  const item = state.item
  if (!item) {
    return (
      <FocusShell state={state} canLeave>
        <Pause>
          <p className="font-semibold">Ответ принят</p>
          <p className="text-sm text-muted">Можно сделать перерыв: таймер запустится, когда вы откроете следующее задание.</p>
          <Button disabled={busy} onClick={openNext}>Следующее задание</Button>
          <ErrorText>{error}</ErrorText>
        </Pause>
      </FocusShell>
    )
  }
  const ai = state.skill_code === 'ai'
  // Подсказка банка про ввод номеров через пробел не нужна: шаги выбираются кликами
  const prompt = item.kind === 'order' ? { ...item.prompt, answer_hint: null } : item.prompt
  const split = prompt.tables.length > 0 || !!prompt.code
  const guard = copyGuard(ai, integrity.copy)
  const label = ai
    ? `Решение ${state.n_answered + 1} из ${state.ai?.total ?? state.n_answered + 1}`
    : `Задание ${state.n_answered + 1}${item.phase === 2 ? ' · уровень выше' : ''}`
  return (
    <FocusShell state={state} canLeave={false} timer={<Timer key={item.seq} seconds={item.remaining_s} onExpire={submit} />}>
      {!ai && integrity.notice && (
        <Notice tone="warning" className="mb-6">
          Вы переключались на другую вкладку. Напоминаем, что в этом тесте нельзя пользоваться ИИ и поиском.{' '}
          <button className="font-semibold underline" onClick={integrity.dismiss}>Понятно</button>
        </Notice>
      )}
      <div className={split ? 'grid items-start gap-10 lg:grid-cols-2' : 'mx-auto grid max-w-3xl gap-8'}>
        <div className="space-y-6" onCopy={guard}>
          <p className="font-mono text-[13px] font-semibold text-primary">{label}</p>
          <PromptText text={prompt.text} />
          <PromptTables tables={prompt.tables} />
        </div>
        <div className="space-y-5 lg:sticky lg:top-6">
          {prompt.code && <div onCopy={guard}><PromptCode code={prompt.code} language={prompt.language} numbered={item.kind === 'verdict'} /></div>}
          <AnswerInput kind={item.kind} prompt={item.prompt} value={value} onChange={setValue} maxRows={state.ai?.sql_max_rows} />
          <PromptHint hint={prompt.answer_hint} />
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="max-w-[320px] text-[13px] leading-snug text-muted">{ai
              ? 'ИИ разрешён. Таймер общий на все решения, перерывов нет.'
              : 'Без ИИ и поиска. Перерыв можно сделать между заданиями.'}</p>
            <Button size="lg" disabled={busy || (item.kind === 'verdict' && !verdictReady(value))} onClick={submit}>Ответить</Button>
          </div>
          <ErrorText>{error}</ErrorText>
          <ReportItem key={item.seq} attemptId={state.id} seq={item.seq} />
        </div>
      </div>
    </FocusShell>
  )
}
