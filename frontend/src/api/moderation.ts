import { api } from './client'

export type SummaryRow = { label: string; value: string }
export type CaseActionOption = { code: string; title: string }
/** Обращение одной очереди (процесс 7): тип сам описывает карточку (`summary`) и кнопки (`actions`), страница о типах не знает. */
export type ModerationCase = {
  id: string; type: string; type_title: string; status: 'open' | 'resolved'; created_at: string; due_at: string | null
  comment: string; resolution: string | null; resolution_text: string | null
  summary: SummaryRow[]; actions: CaseActionOption[]
}
export const getCases = (status: 'open' | 'resolved' = 'open') => api<ModerationCase[]>(`/moderation/cases?status=${status}`)
export const resolveCase = (id: string, action: string, resolution_text: string) =>
  api<ModerationCase>(`/moderation/cases/${id}/resolve`, { method: 'POST', body: { action, resolution_text } })
