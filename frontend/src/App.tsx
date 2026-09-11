import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ContextPage } from './pages/ContextPage'
import { LearnHome } from './pages/LearnHome'
import { LearnLayout } from './pages/LearnLayout'
import { NotesPage } from './pages/NotesPage'
import { PhasePage } from './pages/PhasePage'
import { TaskPage } from './pages/TaskPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/learn" replace />} />
        <Route path="/learn" element={<LearnLayout />}>
          <Route index element={<LearnHome />} />
          <Route path="context" element={<ContextPage />} />
          <Route path="phase/:phaseNumber" element={<PhasePage />} />
          <Route path="phase/:phaseNumber/task/:taskId" element={<TaskPage />} />
          <Route path="phase/:phaseNumber/notes" element={<NotesPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
