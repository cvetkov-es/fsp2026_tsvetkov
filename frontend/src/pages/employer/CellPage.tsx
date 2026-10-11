import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { GRADE_TITLE, type Grade } from '../../api/assessment'
import { getCell, SPEC_TITLE } from '../../api/employer'
import { CandidateCard } from '../../components/employer/CandidateCard'
import { BackLink, Page, PageHeader } from '../../components/ui'

export default function CellPage() {
  const { spec = '', grade = '' } = useParams()
  const q = useQuery({ queryKey: ['cell', spec, grade], queryFn: () => getCell(spec, grade) })
  return (
    <Page>
      <PageHeader back={<BackLink to="/employer/map">Карта категорий</BackLink>}
        title={`${SPEC_TITLE[spec as keyof typeof SPEC_TITLE] ?? spec} · ${GRADE_TITLE[grade as Grade]}`}
        description="Порядок внутри категории: результат теста, достижения ФСП, подтверждения на собеседованиях." />
      <div className="space-y-3">{q.data?.items.map((c) => <CandidateCard key={c.ref} card={c} />)}</div>
    </Page>
  )
}
