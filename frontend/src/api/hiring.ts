import { api } from './client'

export type Stage = 'first' | 'technical' | 'offer' | 'hired' | 'rejected'
export type Level = 'below' | 'meets' | 'above' | 'unknown'
export type VoteState = 'pending' | 'active' | 'disputed' | 'annulled' | 'archived' | 'expired'
export type BoardCard = {
  contact_id: string; alias: string; grade: string | null; revoked: boolean; stage: Stage | null; stage_at: string | null; level: Level | null
  reason: string | null; weak_areas: string[]; vote: { value: Level; state: VoteState; effective_at: string } | null
  vote_note: string | null; chat_open: boolean; area_options: { code: string; title: string }[]
}
export type Board = { need_id: string; title: string; trust_level: string; vote_weight: number | null; votes_used: number; votes_limit: number; dispute_days: number; cards: BoardCard[] }
export type StageInput = { stage: Stage; level?: Level; reason?: string; weak_areas?: string[] }
export type Review = { id: string; company: string; value: Level; grade: string; specialization: string; at: string; state: VoteState; effective_at: string; can_dispute: boolean }
export type DisputeReason = 'no_interview' | 'wrong_stage' | 'wrong_company'

export const STAGE_TITLE: Record<Stage, string> = { first: 'Первичное интервью', technical: 'Техническое интервью', offer: 'Оффер', hired: 'Найм', rejected: 'Отказ' }
export const LEVEL_TITLE: Record<Level, string> = { below: 'ниже ожиданий', meets: 'соответствует ожиданиям', above: 'выше ожиданий', unknown: 'пока не могу сказать' }
export const VOTE_STATE_TITLE: Record<VoteState, string> = {
  pending: 'вступит в силу', active: 'действует', disputed: 'оспорена, на рассмотрении', annulled: 'аннулирована',
  archived: 'в архиве: грейд сменился', expired: 'истекла',
}
export const VOTE_NOTE: Record<string, string> = {
  trust: 'не засчитана: нужен уровень доверия L1 или выше', duplicate: 'не засчитана: оценка вашей компании по этому кандидату уже есть',
  limit: 'не засчитана: месячный лимит оценок исчерпан', disputed: 'сохранена до решения модератора: кандидат её оспорил', annulled: 'не изменена: оценка аннулирована',
}
export const REJECT_REASONS: Record<string, string> = {
  level_below: 'уровень ниже ожиданий', stack: 'не подошёл стек', candidate_declined: 'кандидат отказался',
  other_candidate: 'выбрали другого кандидата', position_closed: 'позицию закрыли', other: 'другое',
}
export const DISPUTE_REASONS: Record<DisputeReason, string> = { no_interview: 'Собеседования не было', wrong_stage: 'Оценка не на этом этапе', wrong_company: 'Не та компания' }

export type HelperQuestion = { text: string; topic: string; reason: string }
export type InterviewHelper = { questions: HelperQuestion[]; used: number; limit: number; window_days: number }

export const getBoard = (needId: string) => api<Board>(`/employer/needs/${needId}/board`)
export const moveStage = (contactId: string, body: StageInput) => api<BoardCard>(`/employer/contacts/${contactId}/stage`, { method: 'POST', body })
export const getInterviewHelper = (contactId: string) => api<InterviewHelper>(`/employer/contacts/${contactId}/interview-helper`)
export const getReviews = () => api<Review[]>('/candidate/reviews')
// answered_at — какую версию оценки оспаривают: если компания успела её изменить, сервер ответит 409
export const disputeReview = (id: string, reason: DisputeReason, comment: string, answered_at: string) =>
  api<Review[]>(`/candidate/reviews/${id}/dispute`, { method: 'POST', body: { reason, comment, answered_at } })
