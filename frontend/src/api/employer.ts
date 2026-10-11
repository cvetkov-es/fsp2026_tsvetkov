import { api } from './client'
import type { Grade, Specialization } from './assessment'
import type { ContactStatus } from './contacts'

export type Format = 'office' | 'hybrid' | 'remote'
export type Employment = 'full' | 'internship' | 'vacation'
export const EMPLOYMENT_TITLE: Record<Employment, string> = { full: 'Полная занятость', internship: 'Стажировка', vacation: 'Каникулярная работа' }
export type Company = { id: string; name: string; description: string | null; industry: string | null; contacts: Record<string, string>; trust_level: string
  domain?: string | null; legal_name?: string | null; l3_pending?: boolean }
export type NeedInput = {
  title: string; specialization: Specialization; grades: Grade[]; must: string[]; nice: string[]; formats: Format[]
  city: string | null; salary_from: number; salary_to: number; gross_net: 'gross' | 'net'; contact_method: 'chat' | 'email' | 'phone'; raw_text?: string | null
  employment?: Employment
}
export type Need = NeedInput & { id: string; status: 'active' | 'closed' }
export type StackItem = { tech: string; state: 'confirmed' | 'declared' }
export type Card = {
  ref: string; alias: string; grade: Grade; grade_status: 'confirmed' | 'not_confirmed'; block: number | null
  fit_level: string | null; readiness: { level: string; tooltip: string } | null; stack: StackItem[]; skills: string[]
  experience_years: number | null; formats: Format[]; city: string | null; conflicts: string[]; pinned: boolean; express: boolean
  filter_mismatch: string | null; interview_badge?: string | null; explanation: { lines: string[]; missing: string[]; counterfactual: string | null }
  contact_status?: ContactStatus | null
  signal?: boolean  // «Хочу к вам» этой компании
  minor?: boolean  // 14–17 лет: стажировка или каникулярная работа
}
export type Selection = {
  blocks: { block: number; title: string; items: Card[] }[]; shortlist: Card[]
  diff: { added: number; removed: { ref: string; alias: string; reason: string }[] } | null  // null — первое открытие
  suggestions: { filter: string; label: string; gain: number }[]
  fork_fit?: { fit: number; total: number }
}
export type Filters = { techs?: string[]; skills?: string[]; has_fsp?: boolean; formats?: Format[] }
export type MapCell = { specialization: Specialization; grade: Grade; confirmed: number; unconfirmed: number }

export const FORMAT_TITLE: Record<Format, string> = { office: 'Офис', hybrid: 'Гибрид', remote: 'Удалёнка' }
export const SPEC_TITLE: Record<Specialization, string> = { backend: 'Backend', frontend: 'Frontend', data: 'Data / Analytics' }
export const SKILL_TITLE: Record<string, string> = {
  sql: 'SQL', devops: 'DevOps и контейнеры', frontend_basics: 'Основы фронтенда', backend_basics: 'Основы бэкенда', ml_basics: 'Основы ML', ai: 'Работа с ИИ',
}
export type DictItem = { canonical: string; category: string; synonyms: string[] }

export const getCompany = () => api<Company | null>('/employer/company')
export const saveCompany = (body: Pick<Company, 'name' | 'description' | 'industry' | 'contacts'>) => api<Company>('/employer/company', { method: 'PUT', body })
export const listNeeds = () => api<Need[]>('/employer/needs')
export const getNeed = (id: string) => api<Need>(`/employer/needs/${id}`)
export const createNeed = (body: NeedInput) => api<Need>('/employer/needs', { method: 'POST', body })
export const updateNeed = (id: string, body: NeedInput) => api<Need>(`/employer/needs/${id}`, { method: 'PUT', body })
export const closeNeed = (id: string) => api<Need>(`/employer/needs/${id}/close`, { method: 'POST' })
export const getStackDict = () => api<DictItem[]>('/stack/dictionary')
export const getMap = () => api<{ cells: MapCell[] }>('/employer/map')
export const getCell = (spec: string, grade: string) => api<{ items: Card[] }>(`/employer/map/${spec}/${grade}`)
export function getSelection(id: string, f: Filters) {
  const q = new URLSearchParams()
  if (f.techs?.length) q.set('techs', f.techs.join(','))
  if (f.skills?.length) q.set('skills', f.skills.join(','))
  if (f.has_fsp) q.set('has_fsp', 'true')
  if (f.formats?.length) q.set('formats', f.formats.join(','))
  const qs = q.toString()
  return api<Selection>(`/employer/needs/${id}/selection${qs ? `?${qs}` : ''}`)
}
export const pin = (id: string, ref: string) => api<void>(`/employer/needs/${id}/shortlist/${ref}`, { method: 'PUT' })
export const unpin = (id: string, ref: string) => api<void>(`/employer/needs/${id}/shortlist/${ref}`, { method: 'DELETE' })
export type NeedDraft = {
  source: 'llm' | 'rules'; title: string | null; specialization: Specialization | null; grades: Grade[]; must: string[]
  nice: string[]; formats: Format[]; city: string | null; salary_from: number | null; salary_to: number | null
  gross_net: 'gross' | 'net' | null; unknown_terms: string[]; missing: string[]
}
export const parseNeed = (text: string) => api<NeedDraft>('/employer/needs/parse', { method: 'POST', body: { text } })
export const getSummary = (needId: string, ref: string) =>
  api<{ text: string; source: 'llm' | 'template' }>(`/employer/needs/${needId}/candidates/${ref}/summary`)
export const candidatePdfUrl = (needId: string, ref: string) => `/api/v1/employer/needs/${needId}/candidates/${ref}/pdf`
