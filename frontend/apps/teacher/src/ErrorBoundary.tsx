import React from 'react'

type Props = {
  children: React.ReactNode
}

type State = {
  error: Error | null
}

const safeClearLocalStorage = () => {
  try {
    window.localStorage.clear()
  } catch {
    // ignore
  }
}

export default class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Keep as console error to avoid silent white screens.
    // eslint-disable-next-line no-console
    console.error('Teacher app crashed', error, info)
  }

  render() {
    if (!this.state.error) return this.props.children
    const message = this.state.error?.message || String(this.state.error)
    return (
      <div style={{ padding: 16, maxWidth: 880, margin: '0 auto', fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif' }}>
        <h1 style={{ fontSize: 18, margin: '8px 0' }}>页面发生错误</h1>
        <p style={{ margin: '8px 0', color: '#444' }}>请尝试刷新页面；如果反复出现，可以清空本地缓存后重试。</p>
        <pre style={{ whiteSpace: 'pre-wrap', background: '#f6f6f6', padding: 12, borderRadius: 8, color: '#222' }}>{message}</pre>
        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <button type="button" onClick={() => window.location.reload()}>
            刷新页面
          </button>
          <button
            type="button"
            onClick={() => {
              safeClearLocalStorage()
              window.location.reload()
            }}
          >
            清空本地缓存并刷新
          </button>
        </div>
      </div>
    )
  }
}

