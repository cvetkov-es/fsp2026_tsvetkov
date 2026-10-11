import type { AttemptState } from './assessment'
import { api } from './client'

export type SkillStatus = 'passed' | 'failed' | 'not_taken'
export type Skill = {
  code: string; title: string; summary: string; techs: string[]; status: SkillStatus; available: boolean
  available_at: string | null; active_attempt_id: string | null; recommended: boolean; bank_ready: boolean
  format: 'test' | 'ai'; items: number; minutes: number | null
}
export const getSkills = () => api<Skill[]>('/candidate/skills')
export const startSkill = (code: string, body: { accept_rules: boolean; pledge: boolean; extra_time: boolean }) =>
  api<AttemptState>(`/candidate/skills/${code}/attempts`, { method: 'POST', body })
