import { useAuth } from '../auth/AuthContext'
import CandidateHome from './candidate/CandidateHome'
import EmployerHome from './employer/EmployerHome'
import LoginPage from './LoginPage'
import ModerationPage from './ModerationPage'

export default function HomePage() {
  const { me, isLoading } = useAuth()
  if (isLoading) return null
  if (!me) return <LoginPage />  // жюри открывает стенд и сразу видит вход и демо-переключатель в шапке
  if (me.role === 'candidate') return <CandidateHome />
  if (me.role === 'moderator' || me.role === 'admin') return <ModerationPage />
  return <EmployerHome />
}
