export type LearnFile = {
  path: string
  language: string
  content: string
}

export type LearnTaskSummary = {
  id: string
  title: string
  done: boolean
  implementation_path: string | null
}

export type LearnPhaseSummary = {
  number: number
  title: string
  status: string
  file: string
  has_implementation: boolean
  task_ids: string[]
}

export type LearnCatalog = {
  phases: LearnPhaseSummary[]
  next_action: string | null
}

export type LearnPhaseDetail = {
  number: number
  title: string
  status: string
  file: string
  markdown: string
  tasks: LearnTaskSummary[]
  has_implementation: boolean
  notes_available: boolean
}

export type LearnTaskDetail = {
  id: string
  title: string
  spec: string
  done: boolean
  implementation: LearnFile | null
}

export type LearnNotes = {
  files: LearnFile[]
}

export type LearnContext = {
  markdown: string
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(`${path} failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const learnApi = {
  catalog: () => getJson<LearnCatalog>('/api/learn/catalog'),
  context: () => getJson<LearnContext>('/api/learn/context'),
  phase: (n: number) => getJson<LearnPhaseDetail>(`/api/learn/phases/${n}`),
  task: (n: number, id: string) =>
    getJson<LearnTaskDetail>(`/api/learn/phases/${n}/tasks/${id}`),
  notes: (n: number) => getJson<LearnNotes>(`/api/learn/phases/${n}/notes`),
}
