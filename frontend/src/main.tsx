import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import AdminApp from './AdminApp'
import './styles/index.css'
import './styles/admin.css'

const RootApp = window.location.pathname.startsWith('/admin') ? AdminApp : App

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RootApp />
  </React.StrictMode>,
)
