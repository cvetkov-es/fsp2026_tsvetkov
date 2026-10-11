import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ContactPage from './pages/ContactPage'
import FspFinishPage from './pages/FspFinishPage'
import GuardianPage from './pages/GuardianPage'
import HomePage from './pages/HomePage'
import HelpPage from './pages/HelpPage'
import LabPage from './pages/LabPage'
import ModerationPage from './pages/ModerationPage'
import CompaniesPage from './pages/candidate/CompaniesPage'
import InvitationsPage from './pages/candidate/InvitationsPage'
import ReviewsPage from './pages/candidate/ReviewsPage'
import ProfileDetailsPage from './pages/candidate/ProfileDetailsPage'
import RulesPage from './pages/candidate/RulesPage'
import SkillsPage from './pages/candidate/SkillsPage'
import SurveyPage from './pages/candidate/SurveyPage'
import TasksPage from './pages/candidate/TasksPage'
import TestRunnerPage from './pages/candidate/TestRunnerPage'
import VacanciesPage from './pages/candidate/VacanciesPage'
import CellPage from './pages/employer/CellPage'
import GroupPage from './pages/employer/GroupPage'
import CompanyForm from './pages/employer/CompanyForm'
import MapPage from './pages/employer/MapPage'
import NeedForm from './pages/employer/NeedForm'
import BoardPage from './pages/employer/BoardPage'
import NeedInvitationsPage from './pages/employer/NeedInvitationsPage'
import SelectionPage from './pages/employer/SelectionPage'
import EmployerTasksPage from './pages/employer/TasksPage'
import TeamsPage from './pages/employer/TeamsPage'
import EmployerVacanciesPage from './pages/employer/VacanciesPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ThreatModelPage from './pages/ThreatModelPage'
import VerifyPage from './pages/VerifyPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="verify" element={<VerifyPage />} />
        <Route path="fsp/finish" element={<FspFinishPage />} />
        <Route path="guardian/:token" element={<GuardianPage />} />
        <Route path="candidate/survey" element={<SurveyPage />} />
        <Route path="candidate/profile" element={<ProfileDetailsPage />} />
        <Route path="candidate/invitations" element={<InvitationsPage />} />
        <Route path="candidate/skills" element={<SkillsPage />} />
        <Route path="candidate/reviews" element={<ReviewsPage />} />
        <Route path="candidate/companies" element={<CompaniesPage />} />
        <Route path="candidate/tasks" element={<TasksPage />} />
        <Route path="candidate/vacancies" element={<VacanciesPage />} />
        <Route path="contacts/:id" element={<ContactPage />} />
        <Route path="test/rules" element={<RulesPage />} />
        <Route path="test/:attemptId" element={<TestRunnerPage />} />
        <Route path="employer/company" element={<CompanyForm />} />
        <Route path="employer/needs/new" element={<NeedForm />} />
        <Route path="employer/needs/:id/edit" element={<NeedForm />} />
        <Route path="employer/needs/:id" element={<SelectionPage />} />
        <Route path="employer/needs/:id/invitations" element={<NeedInvitationsPage />} />
        <Route path="employer/needs/:id/board" element={<BoardPage />} />
        <Route path="moderation" element={<ModerationPage />} />
        <Route path="employer/map" element={<MapPage />} />
        <Route path="employer/map/:spec/:grade" element={<CellPage />} />
        <Route path="employer/teams" element={<TeamsPage />} />
        <Route path="employer/groups/:id" element={<GroupPage />} />
        <Route path="employer/tasks" element={<EmployerTasksPage />} />
        <Route path="employer/vacancies" element={<EmployerVacanciesPage />} />
        <Route path="about/threat-model" element={<ThreatModelPage />} />
        <Route path="help" element={<HelpPage />} />
        <Route path="lab" element={<LabPage />} />
      </Route>
    </Routes>
  )
}
