import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { GRADE_TITLE, type Grade } from '../../api/assessment'
import { ApiError } from '../../api/client'
import { DISPUTE_REASONS, disputeReview, getReviews, LEVEL_TITLE, VOTE_STATE_TITLE, type DisputeReason, type Review } from '../../api/hiring'
import { Button, Card, ErrorText, Page, PageHeader, Pill, Textarea } from '../../components/ui'
import { linkClass } from '../../components/ui-classes'

const day = (iso: string) => new Date(iso).toLocaleDateString('ru-RU')

function DisputeForm({ review, onDone }: { review: Review; onDone: () => void }) {
  const [reason, setReason] = useState<DisputeReason | null>(null)
  const [comment, setComment] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  return (
    <div className="mt-2 space-y-2 rounded-xl bg-surface-2 p-4 text-sm">
      <fieldset>
        <legend className="font-semibold">Оспорить можно, если оценка поставлена по ошибке</legend>
        {(Object.keys(DISPUTE_REASONS) as DisputeReason[]).map((r) => (
          <label key={r} className="mr-3 inline-flex items-center gap-1"><input type="radio" name={`reason-${review.id}`} checked={reason === r} onChange={() => setReason(r)} />{DISPUTE_REASONS[r]}</label>
        ))}
      </fieldset>
      <Textarea aria-label="Комментарий для модератора" maxLength={500} rows={2} value={comment} onChange={(e) => setComment(e.target.value)} />
      <Button disabled={!reason || busy} onClick={async () => {
        setError(null)
        setBusy(true)
        try { await disputeReview(review.id, reason!, comment, review.at); onDone() }
        catch (e) { setError(e instanceof ApiError ? e.title : 'Не удалось отправить спор') } finally { setBusy(false) }
      }}>Оспорить</Button>
      <ErrorText>{error}</ErrorText>
    </div>
  )
}

/** «Мои оценки на собеседованиях» (процесс 2.9): приватный список, спор — до вступления в силу и только по фактам. */
export default function ReviewsPage() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['reviews'], queryFn: getReviews })
  const [open, setOpen] = useState<string | null>(null)
  return (
    <Page narrow>
      <PageHeader title="Мои оценки на собеседованиях"
        description="Оценки видны только вам. Работодателям мы показываем бейдж «Подтверждено на собеседованиях», если он у вас есть. Оценка «ниже ожиданий» не опускает вас в подборке. Оценка начинает действовать через несколько дней после интервью. Пока идёт окно спора, её можно оспорить." />
      {q.isPending && <p>Загрузка…</p>}
      <ErrorText>{q.isError ? (q.error instanceof ApiError ? q.error.title : 'Не удалось загрузить оценки') : null}</ErrorText>
      {q.data?.length === 0 && <Card><p>Оценок пока нет. Они появятся, когда компания отметит итог технического интервью.</p></Card>}
      {q.data?.map((r) => (
        <Card key={r.id}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-semibold">{r.company}</span>
            <Pill tone={r.state === 'active' ? 'success' : r.state === 'annulled' || r.state === 'expired' || r.state === 'archived' ? 'neutral' : 'primary'}>{VOTE_STATE_TITLE[r.state]}{r.state === 'pending' ? ` ${day(r.effective_at)}` : ''}</Pill>
          </div>
          <p className="mt-1 text-sm">Оценка: {LEVEL_TITLE[r.value]} (грейд {GRADE_TITLE[r.grade as Grade] ?? r.grade}) · {day(r.at)}</p>
          {r.can_dispute && <button className={`mt-1 text-sm ${linkClass}`} aria-expanded={open === r.id} onClick={() => setOpen(open === r.id ? null : r.id)}>{open === r.id ? 'Скрыть' : 'Оспорить'}</button>}
          {r.can_dispute && open === r.id && <DisputeForm review={r} onDone={() => { setOpen(null); void qc.invalidateQueries({ queryKey: ['reviews'] }) }} />}
        </Card>
      ))}
    </Page>
  )
}
