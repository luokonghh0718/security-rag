import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import Login from './Login'
import './index.css'

function Root() {
  const [isLoggedIn, setIsLoggedIn] = React.useState(
    () => !!localStorage.getItem('auth_token')
  )

  const handleLoginSuccess = () => {
    setIsLoggedIn(true)
  }

  const handleLogout = () => {
    localStorage.removeItem('auth_token')
    setIsLoggedIn(false)
  }

  if (!isLoggedIn) {
    return <Login onLoginSuccess={handleLoginSuccess} />
  }

  return <App onLogout={handleLogout} />
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
)
