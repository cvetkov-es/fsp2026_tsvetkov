import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { errorText } from '../../api/errors'
import { complainTask, getTasks, submitTask, SUBMISSION_STATUS, type FeedTask } from '../../api/tasks'
import LoadError from '../../components/LoadError'
import { Button, Card } from '../../components/ui'

function Complaint({ task }: { task: FeedTask }) {
  const [open, setOpen] = useState(false)
  const [comment, setComment] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (sent) return <p className="mt-3 text-sm text-muted">Жалоба отправлена. Её рассмотрит модератор.</p>
  if (!open) return <button className="mt-3 text-xs text-muted hover:underline" onClick={() => setOpen(true)}>Пожаловаться: бесплатная работа</button>
  return (
    <div className="mt-3 space-y-2 text-sm">
      <textarea aria-label="Комментарий к жалобе" className="w-full rounded-lg border border-line-strong px-3 py-2" rows={2} maxLength={1000}
        placeholder="Чем задача похожа на реальную работу" value={comment} onChange={(e) => setComment(e.target.value)} />
      <Button type="button" onClick={async () => {
        setError(null)
        try { await complainTask(task.id, comment); setSent(true) } catch (e) { setError(errorText(e)) }
      }}>Отправить жалобу</Button>
      {error && <p role="alert" className="text-danger">{error}</p>}
    </div>
  )
}

function TaskCard({ task, onSent }: { task: FeedTask; onSent: () => void }) {
  const [answer, setAnswer] = useState('')
  const [error, setError] = useState<string | null>(null)
  const mine = task.my_submission
  return (
    <Card>
      <h2 className="text-lg font-semibold">{task.title}</h2>
      <p className="text-sm text-muted">{`${task.company.name} · уровень ${task.company.trust_level} · до ${new Date(task.deadline).toLocaleDateString('ru-RU')}`}</p>
      <p className="mt-2 whitespace-pre-line text-sm">{task.text}</p>
      {task.has_reference && <p className="mt-1 text-xs text-muted">Решение проверим автоматически по эталону компании.</p>}
      {mine ? (
        <p className="mt-3 text-sm"><span className="font-semibold">{`Ваше решение: ${SUBMISSION_STATUS[mine.status] ?? mine.status}`}</span>{mine.comment && ` · ${mine.comment}`}</p>
      ) : (
        <div className="mt-3 space-y-2">
          <textarea aria-label={`Ответ на задачу «${task.title}»`} className="w-full rounded-lg border border-line-strong px-3 py-2" rows={4} maxLength={task.answer_max}
            value={answer} onChange={(e) => setAnswer(e.target.value)} />
          <Button disabled={!answer.trim()} onClick={async () => {
            setError(null)
            try { await submitTask(task.id, answer); onSent() } catch (e) { setError(errorText(e)) }
          }}>Отправить</Button>
          {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        </div>
      )}
      <Complaint task={task} />
    </Card>
  )
}

/** Задачи компаний (процесс 4.6): решение не влияет на грейд; оценённое работодателем — значимая активность. */
export default function TasksPage() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['tasks'], queryFn: () => getTasks() })
  const reload = () => { void qc.invalidateQueries({ queryKey: ['tasks'] }) }
  return (
    <div className="space-y-4 p-6">
      <h1 className="text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">Задачи компаний</h1>
      <p className="text-sm text-muted">Небольшие задачи от компаний. На каждую можно отправить одно решение до срока, на грейд это не влияет. Если задача похожа на бесплатную работу, пожалуйтесь.</p>
      {q.isError && <LoadError error={q.error} />}
      {q.data?.length === 0 && <Card><p>Открытых задач по вашему направлению пока нет.</p></Card>}
      {q.data?.map((t) => <TaskCard key={t.id} task={t} onSent={reload} />)}
    </div>
  )
}
