import { api } from './client'

export type CompanyItem = { id: string; name: string; industry: string | null; description: string | null; trust_level: string; open_needs: number; signal_id: string | null }
export type Companies = { signals_left: number; signals_limit: number; items: CompanyItem[] }
export type Demand = {
  category: string | null; enough: boolean; companies: number | null; min_companies: number; window_days: number
  top: { tech: string; share: number; state: 'confirmed' | 'declared' | 'missing'; skill: string | null }[]
  skills: { code: string; title: string; share: number }[]
}
export type Interest = { ref: string; alias: string; specialization: string; grade: string | null; grade_status: string; at: string }
export const getCompanies = () => api<Companies>('/candidate/companies')
export const sendSignal = (companyId: string) => api<{ signal_id: string; signals_left: number }>(`/candidate/companies/${companyId}/signal`, { method: 'POST' })
export const withdrawSignal = (signalId: string) => api<{ signal_id: string; signals_left: number }>(`/candidate/signals/${signalId}`, { method: 'DELETE' })
export const getDemand = () => api<Demand>('/candidate/demand')
export const getInterest = () => api<Interest[]>('/employer/interest')
