import { api } from './client'

export type Grade = 'junior' | 'middle' | 'senior'
export type Specialization = 'backend' | 'frontend' | 'data'
export type Profile = {
  specialization: Specialization | null
  claimed_grade: Grade | null
  grade_status: 'not_tested' | 'confirmed' | 'not_confirmed'
  confirmed_grade: Grade | null
  status_grade: Grade | null // грейд попытки, которая задала статус
}
export type Meta = {
  specializations: { code: Specialization; title: string; test_available: boolean }[]
  grades: { code: Grade; title: string; description: string }[]
}
export type Cell = string | number | null
export type Prompt = {
  text: string; code: string | null; language: string | null; options: string[] | null
  tables: { name: string; columns: string[]; rows: Cell[][] }[]; steps: string[] | null; answer_hint: string | null
  input_classes?: string[]; clarify?: string[] // только вердикты «Работы с ИИ»
}
export type AnswerKind = 'number' | 'text' | 'choice' | 'line' | 'order' | 'rows' | 'verdict'
export type Item = { seq: number; phase: number; kind: AnswerKind; prompt: Prompt; time_limit_s: number; remaining_s: number; presented_at: string }
export type AiMetrics = {
  passed: boolean | null; n: number; answered: number; correct: number; accuracy: number; miss_weighted: number
  false_reject: number; minutes: number; in_time: boolean
}
export type AiProgress = { total: number; time_left_s: number | null; minutes: number; sql_max_rows: number; pass_accuracy: number; pass_miss: number; cooldown_days?: number }
export type Result = { decision: 'confirmed' | 'not_confirmed'; phrase: string; reliability: number | null; border: boolean; confident: boolean; express: boolean; ai?: AiMetrics | null }
export type Stage = 'phase1' | 'transition' | 'phase2' | 'awaiting_continue' | 'finished' | 'incomplete'
export type AttemptState = {
  id: string; target_grade: Grade | 'skill'; express: boolean; status: string; stage: Stage
  n_answered: number; phase2_total: number; phase2_answered: number; bank_exhausted: boolean; item: Item | null; result: Result | null
  skill_code?: string | null; ai?: AiProgress | null // навык попытки; ai — только «Работа с ИИ»
}
export type Availability = { allowed: boolean; available_at: string | null; reasons: string[] }
export type AttemptSummary = {
  id: string; target_grade: Grade; express: boolean; status: string; decision: string | null
  phrase: string | null; started_at: string; finished_at: string | null
}
export type IntegrityEvent = { type: 'blur' | 'paste' | 'copy'; at: string }

export const GRADE_TITLE: Record<Grade, string> = { junior: 'Junior', middle: 'Middle', senior: 'Senior' }

export const getProfile = () => api<Profile>('/candidate/profile')
export const getMeta = () => api<Meta>('/candidate/meta')
export const saveSurvey = (specialization: Specialization, claimed_grade: Grade) =>
  api<Profile>('/candidate/profile/survey', { method: 'PUT', body: { specialization, claimed_grade } })
export const getAvailability = () => api<Record<Grade, Availability>>('/candidate/tests/availability')
export const listAttempts = () => api<AttemptSummary[]>('/candidate/attempts')
export const startAttempt = (body: { target_grade: Grade; express: boolean; extra_time: boolean; accept_rules: boolean; pledge: boolean }) =>
  api<AttemptState>('/candidate/attempts', { method: 'POST', body })
export const getAttempt = (id: string) => api<AttemptState>(`/candidate/attempts/${id}`)
export const nextItem = (id: string) => api<AttemptState>(`/candidate/attempts/${id}/next`, { method: 'POST' })
export const submitAnswer = (id: string, seq: number, response: unknown, events: IntegrityEvent[]) =>
  api<AttemptState>(`/candidate/attempts/${id}/answer`, { method: 'POST', body: { seq, response, events } })
export const extendAttempt = (id: string) => api<AttemptState>(`/candidate/attempts/${id}/extend`, { method: 'POST' })
export const resetCooldowns = () => api<void>('/demo/reset-cooldowns', { method: 'POST' })
