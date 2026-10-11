import { useState } from 'react'
import { GRADE_TITLE } from '../../api/assessment'
import { ApiError } from '../../api/client'
import { FORMAT_TITLE } from '../../api/employer'
import { uploadResume, type ResumeDraft } from '../../api/profile'
import { Button, ErrorText } from '../ui'

/** PDF-резюме → черновик. Кандидат видит предложения и сам решает, применять ли их (процесс 2.2). */
export function ResumeImport({ onApply }: { onApply: (d: ResumeDraft) => void }) {
  const [draft, setDraft] = useState<ResumeDraft | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return (
    <div className="space-y-3 rounded-xl bg-surface-2 p-4">
      <label htmlFor="resume" className="text-sm font-medium text-ink-2">Заполнить из резюме (PDF до 5 МБ, файл не сохраняется)</label>
      <input id="resume" type="file" accept="application/pdf" disabled={busy} onChange={async (e) => {
        const file = e.target.files?.[0]
        e.target.value = ''  // иначе повторный выбор того же файла (после ошибки) не вызовет onChange
        if (!file) return
        setBusy(true); setError(null); setDraft(null)
        try { setDraft(await uploadResume(file)) } catch (err) { setError(err instanceof ApiError ? err.title : 'Не удалось разобрать файл') } finally { setBusy(false) }
      }} />
      {busy && <p className="text-sm">Разбираем резюме…</p>}
      <ErrorText>{error}</ErrorText>
      {draft && (
        <div className="space-y-1 text-sm">
          <p className="font-semibold">Нашли в резюме ({draft.source === 'llm' ? 'с помощью ИИ' : 'по словарю'}):</p>
          {draft.warnings.map((w) => <p key={w} className="text-danger">{w}</p>)}
          {draft.stack.length > 0 && <p>Стек: {draft.stack.join(', ')}</p>}
          {draft.experience_years != null && <p>Опыт: {draft.experience_years} г.</p>}
          {draft.formats.length > 0 && <p>Формат: {draft.formats.map((f) => FORMAT_TITLE[f]).join(', ')}</p>}
          {draft.city && <p>Город: {draft.city}</p>}
          {draft.full_name && <p>ФИО: {draft.full_name}</p>}
          {Object.keys(draft.contacts).length > 0 && <p>Контакты: {Object.values(draft.contacts).join(', ')}</p>}
          {draft.recommended_grade && <p className="text-muted">Подсказка по грейду: {GRADE_TITLE[draft.recommended_grade]}. Грейд вы выбираете сами и подтверждаете тестом.</p>}
          {draft.unknown_terms.length > 0 && <p className="text-muted">Нет в словаре стека: {draft.unknown_terms.join(', ')}</p>}
          <Button type="button" onClick={() => { onApply(draft); setDraft(null) }}>Применить к профилю</Button>
        </div>
      )}
    </div>
  )
}
