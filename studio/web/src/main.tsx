import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import { IS_MOCK, useMockApi } from './api'

async function boot() {
  if (IS_MOCK) {
    const { mockApi } = await import('./mock/mockApi')
    useMockApi(mockApi)
  }
  const { default: App } = await import('./App')
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
}
boot()
