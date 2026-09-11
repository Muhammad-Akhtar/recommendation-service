import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

type Props = {
  markdown: string
}

export function MarkdownView({ markdown }: Props) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
          code: ({ className, children, ...props }) => {
            const text = String(children)
            const inline = !className && !text.includes('\n')
            if (inline) {
              return (
                <code className="inline-code" {...props}>
                  {children}
                </code>
              )
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            )
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  )
}

export function StatusBadge({ status }: { status: string }) {
  const kind = status.toLowerCase().replace(/\s+/g, '-')
  return <span className={`badge badge-${kind}`}>{status}</span>
}

export function Loading({ children }: { children?: ReactNode }) {
  return <p className="muted">{children ?? 'Loading…'}</p>
}

export function ErrorMsg({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : 'Request failed'
  return <p className="error">{message}</p>
}
