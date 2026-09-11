import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { learnApi, type LearnPhaseDetail, type LearnTaskDetail } from '../api/learn'
import { CodeView } from '../components/CodeView'
import { ErrorMsg, Loading, MarkdownView } from '../components/MarkdownView'

export function TaskPage() {
  const { phaseNumber, taskId } = useParams()
  const [task, setTask] = useState<LearnTaskDetail | null>(null)
  const [phase, setPhase] = useState<LearnPhaseDetail | null>(null)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    const n = Number(phaseNumber)
    const id = taskId ?? ''
    setTask(null)
    setError(null)
    Promise.all([learnApi.task(n, id), learnApi.phase(n)])
      .then(([t, p]) => {
        setTask(t)
        setPhase(p)
      })
      .catch(setError)
  }, [phaseNumber, taskId])

  if (error) return <ErrorMsg error={error} />
  if (!task || !phase) return <Loading />

  const index = phase.tasks.findIndex((item) => item.id === task.id)
  const prev = index > 0 ? phase.tasks[index - 1] : null
  const next = index >= 0 && index < phase.tasks.length - 1 ? phase.tasks[index + 1] : null
  const n = Number(phaseNumber)

  return (
    <article>
      <p className="kicker">
        <Link to={`/learn/phase/${n}`}>Phase {n}</Link>
      </p>
      <h1>
        Task {task.id} — {task.title}
      </h1>
      <section>
        <h2>Spec</h2>
        <MarkdownView markdown={task.spec} />
      </section>
      <section>
        <h2>Implementation</h2>
        {task.implementation ? (
          <CodeView file={task.implementation} />
        ) : (
          <p className="muted">Implementation not started</p>
        )}
      </section>
      <nav className="pager">
        {prev ? (
          <Link to={`/learn/phase/${n}/task/${prev.id}`}>Previous: {prev.id}</Link>
        ) : (
          <span />
        )}
        {next ? (
          <Link to={`/learn/phase/${n}/task/${next.id}`}>Next: {next.id}</Link>
        ) : (
          <span />
        )}
      </nav>
    </article>
  )
}
