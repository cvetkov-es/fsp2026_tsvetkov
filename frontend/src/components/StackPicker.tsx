import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { getStackDict } from '../api/employer'
import { Chip, Input } from './ui'

export function StackPicker({ value, onChange, label }: { value: string[]; onChange: (v: string[]) => void; label: string }) {
  const dict = useQuery({ queryKey: ['stack-dict'], queryFn: getStackDict })
  const [q, setQ] = useState('')
  const needle = q.trim().toLowerCase()
  // Ищем и по каноническому названию, и по синонимам: «k8s» → Kubernetes, «реакт» → React
  const options = (dict.data ?? [])
    .filter((d) => !value.includes(d.canonical) && [d.canonical, ...(d.synonyms ?? [])].some((n) => n.toLowerCase().includes(needle)))
    .map((d) => d.canonical).slice(0, 8)
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-ink-2" htmlFor={`stack-${label}`}>{label}</label>
      <div className="flex flex-wrap gap-2">{value.map((t) => (
        <button type="button" key={t} onClick={() => onChange(value.filter((x) => x !== t))} className="rounded-full border border-line-strong bg-white px-3 py-1 text-sm">{t} ×</button>
      ))}</div>
      <Input id={`stack-${label}`} placeholder="Начните вводить: postgres, k8s, реакт…" value={q} onChange={(e) => setQ(e.target.value)} />
      {q && <div className="flex flex-wrap gap-2">{options.map((o) => (
        <Chip key={o} onClick={() => { onChange([...value, o]); setQ('') }}>{o}</Chip>
      ))}</div>}
    </div>
  )
}
