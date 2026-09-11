import type { LearnFile } from '../api/learn'

export function CodeView({ file }: { file: LearnFile }) {
  return (
    <div className="code-block">
      <div className="code-path">{file.path}</div>
      <pre>
        <code>{file.content}</code>
      </pre>
    </div>
  )
}
