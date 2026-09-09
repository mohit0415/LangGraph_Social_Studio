import './App.css'
import { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { BrowserRouter as ApiRouter, Navigate, Route, Routes } from 'react-router-dom'

import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Studio from './pages/Studio'
import ProtectedRoute from './routes/ProtectedRoute'
import PublicRoute from './routes/PublicRoute'
import { AUTH_LOGOUT } from './store/authReducer'
import { fetchSession } from './utils/studio_api'

function App() {
  const dispatch = useDispatch()
  const isAuthenticated = useSelector((s) => s.auth.isAuthenticated)

  // Sessions live in the backend's memory, so a restart or a long idle wipes
  // them while this tab still looks signed in. Check once on boot and send the
  // user back to the login page before they hit a 401 mid-generation.
  useEffect(() => {
    if (!isAuthenticated) return undefined

    let cancelled = false
    fetchSession().then((res) => {
      if (cancelled) return
      if (res.ok && !res.authenticated) dispatch({ type: AUTH_LOGOUT })
    })

    return () => {
      cancelled = true
    }
  }, [isAuthenticated, dispatch])

  return (
    <ApiRouter>
      <Routes>
        <Route element={<PublicRoute />}>
          <Route element={<Login />} path='/' />
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route element={<Studio />} path='/studio' />
          <Route element={<Dashboard />} path='/dashboard' />
        </Route>

        <Route element={<Navigate to='/' replace />} path='*' />
      </Routes>
    </ApiRouter>
  )
}

export default App
