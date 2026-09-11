import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { learnApi, type LearnCatalog } from '../api/learn'
import { ErrorMsg, Loading, StatusBadge } from '../components/MarkdownView'

export function LearnHome() {
  const [catalog, setCatalog] = useState<LearnCatalog | null>(null)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    learnApi.catalog().then(setCatalog).catch(setError)
  }, [])

  if (error) return <ErrorMsg error={error} />
  if (!catalog) return <Loading />

  return (
    <article>
      <h1>ML learning plan</h1>
      {catalog.next_action && (
        <p className="next-action">{catalog.next_action}</p>
      )}
      <p className="muted">
        Notes and code stay in the repo. This page reads them from the API.
      </p>
      <table className="phase-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Topic</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {catalog.phases.map((phase) => (
            <tr key={phase.number}>
              <td>{phase.number}</td>
              <td>
                <Link to={`/learn/phase/${phase.number}`}>{phase.title}</Link>
              </td>
              <td>
                <StatusBadge status={phase.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  )
}
