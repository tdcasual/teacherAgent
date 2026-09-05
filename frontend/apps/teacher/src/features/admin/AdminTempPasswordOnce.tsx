import { useState } from 'react'

export default function AdminTempPasswordOnce({
  password,
  onCopied,
}: {
  password: string
  onCopied?: () => void
}) {
  const [copied, setCopied] = useState(false)
  if (!password) return null
  return (
    <div className="grid gap-1.5 rounded-lg border border-border bg-white p-3">
      <div className="text-xs text-muted">一次性临时密码，请立即复制发给当事人。</div>
      <div className="font-mono text-sm break-all">{password}</div>
      {copied ? (
        <div className="text-xs text-muted">已复制</div>
      ) : (
        <button
          type="button"
          className="ghost justify-start w-fit"
          onClick={() => {
            void navigator.clipboard.writeText(password).then(() => {
              setCopied(true)
              onCopied?.()
            })
          }}
        >
          复制一次
        </button>
      )}
    </div>
  )
}
