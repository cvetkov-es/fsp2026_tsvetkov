import { api } from './client'

// Пустая корзина на малой популяции приходит как null (бэкенд заменяет NaN): страница показывает прочерк
type N = number | null
export type Headline = { key: string; title: string; value: N; format: 'percent' | 'number'; note: string }
export type OcPoint = { delta: number; full: number; express_confirmed: number; express_undecided: number }
export type NdcgBar = { key: string; title: string; mean: N; ci_low: N; ci_high: N; group: 'ranker' | 'ablation' }
export type Metric = { mean: N; ci_low: N; ci_high: N }
export type AiPolicy = { key: string; title: string; pass_rate: N; accuracy: N; miss_weighted: N; false_reject: N; minutes: N }
export type AiPolicies = { attempts: number; model: string; llm: 'ok' | 'skipped'; policies: AiPolicy[] }
export type LabResults = {
  generated_at: string; population: number; duration_s: number; headline: Headline[]
  charts: { oc_curve: OcPoint[]; ndcg_bars: NdcgBar[] }
  test: {
    accuracy: N; retest_kappa: N; express_decided_share: N; accuracy_express_decided: N
    by_grade: Record<string, { n: number; false_positive: N; false_negative: N; len_full: { mean: N; p90: N }; len_express: { mean: N } }>
    kappa_by_distance: { dist_from: number; dist_to: number | null; n: number; agreement: N; kappa: N }[]
    leak: { honest_false_positive: N; static_bank_false_positive: N; generated_bank_false_positive: N; leaked_share: number }
  }
  matching: {
    rankers: Record<string, { all: Record<'ndcg' | 'p_at_k' | 'mrr', Metric>; holdout: Record<'ndcg', Metric> }>
    paired: { case: string; passed: boolean }[]; blocks: Record<string, boolean>; invariance: Record<string, number>
    sensitivity: { param: string; factor: number; ndcg_delta: N; top10_tau: N; top10_overlap: N }[]
    fairness: { by_test_tier: { test_tier: number; rate_no_fsp: N; rate_fsp: N; ratio: N }[]; farmers_share_top10: N; farmers_share_relevant: N }
  }
  calibration: { shift: number; by_n: { n: number; expert_error: number; observed_error: N; calibrated_error: N }[] }
  market: Record<string, { invitations: number; acceptance_rate: number; below_threshold_share: number; needs_filled_share: number; invites_per_candidate_p95: N; invites_per_need: number; hired_relevance: N; fork_raised_share: number }>
  llm: Record<string, Record<string, unknown>>
  ai_skill_policies?: AiPolicies | { skipped: string } | { error: string } // в отчётах до плана 07a3 — skipped
}
export type RunBrief = { id: string; kind: string; population: number; status: 'queued' | 'running' | 'done' | 'failed'; error: string | null; created_at: string; finished_at: string | null }
export type LabLatest = { run: RunBrief | null; results: LabResults | null; active: RunBrief | null; failed: RunBrief | null; max_population: number }
export const getLabLatest = () => api<LabLatest>('/lab/latest')
// Пока прогон идёт, страница опрашивает только его статус, а не весь отчёт
export const getLabRun = (id: string) => api<RunBrief>(`/lab/runs/${id}`)
export const startLabRun = (population: number) => api<RunBrief>('/lab/runs', { method: 'POST', body: { population } })
