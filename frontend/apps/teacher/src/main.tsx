import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import ErrorBoundary from './ErrorBoundary'
import { resolveRuntimeApiBase } from '../../shared/apiBase'
import { installAuthFetchInterceptor } from '../../shared/authFetch'
import { safeLocalStorageGetItem } from '../../shared/storage'
import { clearTeacherAuthSession } from './features/auth/teacherAuth'
import './tailwind.css'
import '../../shared/dialog.css'
import '../../shared/mobile/mobile.css'

installAuthFetchInterceptor('teacherAuthAccessToken', {
  onUnauthorized: () => {
    clearTeacherAuthSession()
  },
  apiBase: resolveRuntimeApiBase(safeLocalStorageGetItem('apiBaseTeacher')),
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
)
