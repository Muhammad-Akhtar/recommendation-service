import { useEffect, useState } from 'react'
import { learnApi, type LearnContext } from '../api/learn'
import { ErrorMsg, Loading, MarkdownView } from '../components/MarkdownView'

export function ContextPage() {
  const [data, setData] = useState<LearnContext | null>(null)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    learnApi.context().then(setData).catch(setError)
  }, [])

  if (error) return <ErrorMsg error={error} />
  if (!data) return <Loading />

  return (
    <article>
      <h1>ML context</h1>
      <MarkdownView markdown={data.markdown} />
    </article>
  )
}
