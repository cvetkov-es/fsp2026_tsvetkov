import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { LabLatest, LabResults, RunBrief } from '../api/lab'
import LabPage from '../pages/LabPage'

const m = (mean: number) => ({ mean, ci_low: mean - 0.05, ci_high: mean + 0.05 })
const market = (invites: number) => ({ invitations: invites, acceptance_rate: 0.73, below_threshold_share: 0.16, needs_filled_share: 1, invites_per_candidate_p95: 4, invites_per_need: invites / 30, hired_relevance: 1.33, fork_raised_share: 0 })
const results: LabResults = {
  generated_at: '2026-10-08T00:00:00Z', population: 3000, duration_s: 120,
  headline: [
    { key: 'accuracy_far', title: 'Верные решения теста', value: 0.95, format: 'percent', note: 'вдали от порога' },
    { key: 'retest', title: 'Повторный тест даёт то же решение', value: 0.72, format: 'percent', note: 'κ' },
    { key: 'ndcg', title: 'Качество подборки, nDCG@10', value: 0.68, format: 'number', note: 'бейзлайн 0.45' },
    { key: 'leak', title: 'Ложные подтверждения при утечке трети банка', value: 0.085, format: 'percent', note: 'статичный 40%' },
  ],
  charts: { oc_curve: [{ delta: -2, full: 0, express_confirmed: 0, express_undecided: 0.2 }, { delta: 2, full: 1, express_confirmed: 0.9, express_undecided: 0.1 }],
    ndcg_bars: [{ key: 'ours', title: 'Наше ранжирование', mean: 0.68, ci_low: 0.62, ci_high: 0.74, group: 'ranker' }] },
  test: { accuracy: 0.82, retest_kappa: 0.33, express_decided_share: 0.32, accuracy_express_decided: 0.93,
    by_grade: { middle: { n: 1000, false_positive: 0.05, false_negative: 0.18, len_full: { mean: 12.2, p90: 15 }, len_express: { mean: 7.9 } },
      senior: { n: 0, false_positive: null, false_negative: null, len_full: { mean: null, p90: null }, len_express: { mean: null } } },
    kappa_by_distance: [{ dist_from: 1, dist_to: null, n: 60, agreement: 1, kappa: 1 }],
    leak: { honest_false_positive: 0.085, static_bank_false_positive: 0.4, generated_bank_false_positive: 0.085, leaked_share: 0.3 } },
  matching: { rankers: { ours: { all: { ndcg: m(0.68), p_at_k: m(0.38), mrr: m(0.8) }, holdout: { ndcg: m(0.74) } } },
    paired: [{ case: 'Сильный тест без ФСП выше слабого теста с ФСП (случай 1)', passed: true }],
    blocks: { each_candidate_one_block: true, unconfirmed_never_above_confirmed: true },
    invariance: { city_changed_same_order_share: 1, pseudonym_changed_same_order_share: 1 },
    sensitivity: [], fairness: { by_test_tier: [{ test_tier: 2, rate_no_fsp: 0.06, rate_fsp: 0.09, ratio: 0.73 }], farmers_share_top10: 0.05, farmers_share_relevant: 0.048 } },
  calibration: { shift: 0.3, by_n: [{ n: 300, expert_error: 0.3, observed_error: 0.12, calibrated_error: 0.12 }] },
  market: { ours: market(300), no_quota: market(1850) },
  llm: {},
}
const done: RunBrief = { id: 'r', kind: 'validate', population: 3000, status: 'done', error: null, created_at: '', finished_at: '2026-10-08T00:00:00Z' }
const latest = (over: Partial<LabLatest> = {}): LabLatest => ({ run: done, results, active: null, failed: null, max_population: 3000, ...over })

const api = vi.hoisted(() => ({
  getLabLatest: vi.fn<() => Promise<LabLatest>>(),
  getLabRun: vi.fn<(id: string) => Promise<RunBrief>>(),
  startLabRun: vi.fn<(n: number) => Promise<RunBrief>>(),
}))
vi.mock('../api/lab', async (orig) => ({ ...(await orig<typeof import('../api/lab')>()), ...api }))
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ me: { id: 'u', email: 'jury@example.ru', role: 'candidate', is_demo: false } }) }))

const show = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><LabPage /></MemoryRouter></QueryClientProvider>)

beforeEach(() => {
  vi.clearAllMocks()
  api.getLabLatest.mockResolvedValue(latest())
  api.startLabRun.mockResolvedValue({ ...done, kind: 'ui', status: 'queued' })
})

describe('LabPage', () => {
  it('compares three AI-skill policies when the report has them', async () => {
    const row = (key: string, title: string, pass_rate: number) => ({ key, title, pass_rate, accuracy: 0.5, miss_weighted: 1, false_reject: 0, minutes: 1 })
    api.getLabLatest.mockResolvedValue(latest({ results: { ...results, ai_skill_policies: { attempts: 5, model: 'm', llm: 'skipped',
      policies: [row('trust_all', 'Принимает всё', 0)] } } }))
    show()
    expect(await screen.findByRole('cell', { name: 'Принимает всё' })).toBeInTheDocument()
    expect(screen.getByText(/считаются при прогоне/)).toBeInTheDocument()
  })

  it('shows four headline numbers, two charts, checks and starts a background run', async () => {
    show()
    expect(await screen.findByText('95%')).toBeInTheDocument()
    expect(screen.getByText('0.68', { selector: 'p' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Кривая решений теста' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'nDCG@10 по ранжировщикам' })).toBeInTheDocument()
    expect(screen.getByText(/✓ Сильный тест без ФСП/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Запустить прогон' }))
    expect(api.startLabRun).toHaveBeenCalledWith(500)
  })

  it('names rankers and market variants in Russian and shows empty bins as dashes', async () => {
    show()
    expect(await screen.findByRole('cell', { name: 'Наше ранжирование' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Без квоты' })).toBeInTheDocument()
    expect(screen.getByRole('row', { name: /senior 0 — — — \/ — —/ })).toBeInTheDocument()
  })

  it('tells about a failed run instead of silently showing the old result', async () => {
    api.getLabLatest.mockResolvedValue(latest({ failed: { ...done, id: 'f', kind: 'ui', population: 500, status: 'failed', error: 'stale' } }))
    show()
    expect(await screen.findByRole('alert')).toHaveTextContent('Прогон на 500 кандидатов не завершился')
    expect(screen.getByText('95%')).toBeInTheDocument()
  })

  it('shows loading and a load error instead of «no runs yet»', async () => {
    api.getLabLatest.mockRejectedValue(new ApiError(500, 'internal_error', 'Ошибка на сервере. Попробуйте позже'))
    show()
    expect(screen.getByText('Загрузка…')).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent('Ошибка на сервере. Попробуйте позже')
    expect(screen.queryByText(/Прогонов пока нет/)).not.toBeInTheDocument()
  })

  it('checks the population range on the client and blocks double submit', async () => {
    api.getLabLatest.mockResolvedValue(latest({ max_population: 2000 }))
    let finish: (v: RunBrief) => void = () => {}
    api.startLabRun.mockReturnValue(new Promise((resolve) => { finish = resolve }))
    show()
    const input = await screen.findByLabelText('Размер популяции')
    await userEvent.clear(input)
    await userEvent.type(input, '2500')
    await userEvent.click(screen.getByRole('button', { name: 'Запустить прогон' }))
    expect(screen.getByRole('alert')).toHaveTextContent('от 100 до 2000')
    expect(api.startLabRun).not.toHaveBeenCalled()
    await userEvent.clear(input)
    await userEvent.type(input, '500')
    await userEvent.click(screen.getByRole('button', { name: 'Запустить прогон' }))
    expect(screen.getByRole('button', { name: 'Запустить прогон' })).toBeDisabled()
    finish({ ...done, kind: 'ui', status: 'queued' })
    expect(api.startLabRun).toHaveBeenCalledTimes(1)
  })

  it('polls only the active run and reloads results when it finishes', async () => {
    api.getLabLatest.mockResolvedValueOnce(latest({ active: { ...done, id: 'a', kind: 'ui', population: 500, status: 'running', finished_at: null } }))
    api.getLabRun.mockResolvedValue({ ...done, id: 'a', kind: 'ui', population: 500, status: 'done' })
    show()
    expect(await screen.findByText(/Идёт прогон на 500 кандидатов/)).toBeInTheDocument()
    await waitFor(() => expect(api.getLabRun).toHaveBeenCalledWith('a'))
    await waitFor(() => expect(api.getLabLatest).toHaveBeenCalledTimes(2))
    expect(await screen.findByRole('button', { name: 'Запустить прогон' })).toBeInTheDocument()
  })
})
