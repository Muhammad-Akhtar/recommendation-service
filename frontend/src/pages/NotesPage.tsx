import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { learnApi, type LearnNotes } from '../api/learn'
import { ErrorMsg, Loading, MarkdownView } from '../components/MarkdownView'

export function NotesPage() {
  const { phaseNumber } = useParams()
  const [notes, setNotes] = useState<LearnNotes | null>(null)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    const n = Number(phaseNumber)
    setNotes(null)
    setError(null)
    learnApi.notes(n).then(setNotes).catch(setError)
  }, [phaseNumber])

  if (error) return <ErrorMsg error={error} />
  if (!notes) return <Loading />

  const n = Number(phaseNumber)
  return (
    <article>
      <p className="kicker">
        <Link to={`/learn/phase/${n}`}>Phase {n}</Link>
      </p>
      <h1>Notes</h1>
      {notes.files.map((file) => (
        <section key={file.path}>
          <p className="code-path">{file.path}</p>
          <MarkdownView markdown={file.content} />
        </section>
      ))}
    </article>
  )
}
