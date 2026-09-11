import { NavLink } from 'react-router-dom'
import type { LearnCatalog, LearnPhaseDetail } from '../api/learn'
import { StatusBadge } from './MarkdownView'

type Props = {
  catalog: LearnCatalog | null
  phase?: LearnPhaseDetail | null
}

export function LearnSidebar({ catalog, phase }: Props) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <NavLink to="/learn">Learn</NavLink>
        <p className="muted small">ML revision</p>
      </div>
      <nav>
        <NavLink to="/learn" end>
          Overview
        </NavLink>
        <NavLink to="/learn/context">Context</NavLink>
      </nav>
      <h2>Phases</h2>
      <nav className="phase-nav">
        {catalog?.phases.map((item) => (
          <NavLink key={item.number} to={`/learn/phase/${item.number}`}>
            <span className="phase-num">{item.number}</span>
            <span className="phase-title">{item.title}</span>
            <StatusBadge status={item.status} />
          </NavLink>
        ))}
      </nav>
      {phase && phase.tasks.length > 0 && (
        <>
          <h2>On this phase</h2>
          <nav>
            {phase.tasks.map((task) => (
              <NavLink
                key={task.id}
                to={`/learn/phase/${phase.number}/task/${task.id}`}
              >
                {task.id} {task.title}
              </NavLink>
            ))}
            {phase.notes_available && (
              <NavLink to={`/learn/phase/${phase.number}/notes`}>Notes</NavLink>
            )}
          </nav>
        </>
      )}
    </aside>
  )
}
