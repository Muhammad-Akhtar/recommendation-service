import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { learnApi, type LearnPhaseDetail } from '../api/learn'
import { ErrorMsg, Loading, MarkdownView, StatusBadge } from '../components/MarkdownView'

export function PhasePage() {
  const { phaseNumber } = useParams()
  const [phase, setPhase] = useState<LearnPhaseDetail | null>(null)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    const n = Number(phaseNumber)
    setPhase(null)
    setError(null)
    learnApi.phase(n).then(setPhase).catch(setError)
  }, [phaseNumber])

  if (error) return <ErrorMsg error={error} />
  if (!phase) return <Loading />

  return (
    <article>
      <p className="kicker">
        Phase {phase.number} <StatusBadge status={phase.status} />
      </p>
      <h1>{phase.title}</h1>
      {phase.tasks.length > 0 && (
        <ul className="task-index">
          {phase.tasks.map((task) => (
            <li key={task.id}>
              <Link to={`/learn/phase/${phase.number}/task/${task.id}`}>
                Task {task.id} — {task.title}
              </Link>
              {task.done ? ' (done)' : ''}
            </li>
          ))}
        </ul>
      )}
      {phase.notes_available && (
        <p>
          <Link to={`/learn/phase/${phase.number}/notes`}>Phase notes</Link>
        </p>
      )}
      <MarkdownView markdown={phase.markdown} />
    </article>
  )
}
