import { useEffect, useState } from 'react'
import { Outlet, useParams } from 'react-router-dom'
import {
  learnApi,
  type LearnCatalog,
  type LearnPhaseDetail,
} from '../api/learn'
import { LearnSidebar } from '../components/LearnSidebar'
import { ErrorMsg, Loading } from '../components/MarkdownView'

export function LearnLayout() {
  const { phaseNumber } = useParams()
  const [catalog, setCatalog] = useState<LearnCatalog | null>(null)
  const [phase, setPhase] = useState<LearnPhaseDetail | null>(null)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    learnApi.catalog().then(setCatalog).catch(setError)
  }, [])

  useEffect(() => {
    if (!phaseNumber) {
      setPhase(null)
      return
    }
    const n = Number(phaseNumber)
    learnApi
      .phase(n)
      .then(setPhase)
      .catch(() => setPhase(null))
  }, [phaseNumber])

  if (error) {
    return (
      <div className="shell">
        <ErrorMsg error={error} />
      </div>
    )
  }

  if (!catalog) {
    return (
      <div className="shell">
        <Loading />
      </div>
    )
  }

  return (
    <div className="shell">
      <LearnSidebar catalog={catalog} phase={phase} />
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
