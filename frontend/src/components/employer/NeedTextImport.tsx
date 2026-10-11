import { useState } from 'react'
import { ApiError } from '../../api/client'
import { parseNeed, type NeedDraft } from '../../api/employer'
import { Button, ErrorText, Textarea } from '../ui'

/** Текст вакансии → черновик формы. Поля потом проверяются и правятся в обычной форме (процесс 4.2). */
export function NeedTextImport({ onDraft }: { onDraft: (draft: NeedDraft, text: string) => void }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return (
    <div className="mb-6 space-y-2 rounded-xl bg-surface-2 p-4">
      <label htmlFor="need-text" className="text-sm font-medium text-ink-2">Есть текст вакансии? Вставьте его, и мы заполним форму</label>
      <Textarea id="need-text" rows={5} maxLength={8000} value={text} onChange={(e) => setText(e.target.value)} />
      <ErrorText>{error}</ErrorText>
      <Button type="button" variant="secondary" disabled={busy || text.trim().length < 20} onClick={async () => {
        setBusy(true); setError(null)
        try { onDraft(await parseNeed(text), text) } catch (e) { setError(e instanceof ApiError ? e.title : 'Не удалось разобрать текст') } finally { setBusy(false) }
      }}>{busy ? 'Разбираем…' : 'Заполнить по тексту'}</Button>
    </div>
  )
}
