import { api } from './client'

export type ItemReason = 'wrong_key' | 'unclear' | 'typo' | 'other'
export const ITEM_REASON_TITLE: Record<ItemReason, string> = {
  wrong_key: 'Ключ ответа неверен', unclear: 'Условие непонятно', typo: 'Опечатка', other: 'Другое',
}
export type MyCase = {
  id: string; type: string; type_title: string; status: 'open' | 'resolved'; created_at: string; due_at: string | null
  outcome: string | null; resolution_text: string | null
}

export const reportItem = (attemptId: string, seq: number, body: { reason: ItemReason; comment: string }) =>
  api<{ ok: boolean }>(`/candidate/attempts/${attemptId}/items/${seq}/report`, { method: 'POST', body })
export const objectToDecision = (attemptId: string, comment: string) =>
  api<{ case_id: string; due_at: string }>(`/candidate/attempts/${attemptId}/objection`, { method: 'POST', body: { comment } })
export const getMyCases = () => api<MyCase[]>('/candidate/cases')
