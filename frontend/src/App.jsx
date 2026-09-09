import './App.css'
import { BrowserRouter as ApiRouter, Navigate, Route, Routes } from 'react-router-dom'

import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Studio from './pages/Studio'
import ProtectedRoute from './routes/ProtectedRoute'
import PublicRoute from './routes/PublicRoute'

function App() {
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
