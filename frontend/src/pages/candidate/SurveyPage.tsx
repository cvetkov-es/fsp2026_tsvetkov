import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMeta, getProfile, saveSurvey, type Grade, type Specialization } from '../../api/assessment'
import { ApiError } from '../../api/client'
import { Button, Card, ErrorText, Page, PageHeader } from '../../components/ui'

export default function SurveyPage() {
  const nav = useNavigate()
  const meta = useQuery({ queryKey: ['meta'], queryFn: getMeta })
  const profile = useQuery({ queryKey: ['profile'], queryFn: getProfile })
  const [spec, setSpec] = useState<Specialization | null>(null)
  const [grade, setGrade] = useState<Grade | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const qc = useQueryClient()
  const s = spec ?? profile.data?.specialization ?? null
  const g = grade ?? profile.data?.claimed_grade ?? null
  return (
    <Page narrow>
      <PageHeader title="Ваше направление" description="Грейд подтверждается тестом. Если сменить направление, подтверждённый грейд сбросится." />
      <Card className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-3">
          {meta.data?.specializations.map((x) => (
            <button key={x.code} type="button" aria-pressed={s === x.code} onClick={() => setSpec(x.code)}
              className={`rounded-2xl border-[1.5px] p-4 text-left font-semibold transition ${s === x.code ? 'border-primary bg-primary-tint' : 'border-line hover:border-primary-line'}`}>
              {x.title}{!x.test_available && <span className="mt-1 block text-xs font-normal text-muted">тест готовится</span>}
            </button>
          ))}
        </div>
        <fieldset className="space-y-2">
          <legend className="mb-3 text-lg font-semibold">На какой грейд претендуете</legend>
          {meta.data?.grades.map((x) => (
            <label key={x.code} className={`flex cursor-pointer gap-3 rounded-2xl border-[1.5px] p-4 transition ${g === x.code ? 'border-primary bg-primary-tint' : 'border-line hover:border-primary-line'}`}>
              <input type="radio" name="grade" className="mt-1" checked={g === x.code} onChange={() => setGrade(x.code)} />
              <span><span className="font-semibold">{x.title}</span><br /><span className="text-sm text-muted">{x.description}</span></span>
            </label>
          ))}
        </fieldset>
        <ErrorText>{error}</ErrorText>
        <Button size="lg" disabled={!s || !g || busy} onClick={async () => {
          setBusy(true)
          setError(null)
          try {
            await saveSurvey(s!, g!)
            await qc.invalidateQueries()
            nav('/')
          } catch (e) { setError(e instanceof ApiError ? e.title : 'Не удалось связаться с сервером') } finally { setBusy(false) }
        }}>Сохранить</Button>
      </Card>
    </Page>
  )
}
