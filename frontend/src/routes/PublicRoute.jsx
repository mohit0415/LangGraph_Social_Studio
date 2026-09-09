import React from 'react'
import { useSelector } from 'react-redux'
import { Navigate, Outlet } from 'react-router-dom'

const PublicRoute = ({ redirectTo = '/studio' }) => {
  const isAuthenticated = useSelector((s) => s.auth.isAuthenticated)

  if (isAuthenticated) {
    return <Navigate to={redirectTo} replace />
  }

  return <Outlet />
}

export default PublicRoute
