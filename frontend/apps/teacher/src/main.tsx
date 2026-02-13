import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import ErrorBoundary from './ErrorBoundary'
import { installAuthFetchInterceptor } from '../../shared/authFetch'
import './tailwind.css'
import '../../shared/dialog.css'

installAuthFetchInterceptor('teacherAuthAccessToken')

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
)
