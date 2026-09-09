import React, { useState } from 'react'
import { useDispatch } from 'react-redux'
import { useNavigate, useLocation } from 'react-router-dom'
import { AUTH_LOGIN } from '../store/authReducer'

const Login = () => {
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')

  const dispatch = useDispatch()
  const navigate = useNavigate()
  const location = useLocation()

  const from = location.state?.from?.pathname || '/studio'

  const update = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const handleSubmit = (e) => {
    e.preventDefault()

    if (!form.email.trim() || !form.password) {
      setError('Enter your email and password.')
      return
    }

    setError('')
    dispatch({ type: AUTH_LOGIN, payload: { email: form.email.trim() } })
    navigate(from, { replace: true })
  }

  const fieldClass =
    'w-full rounded-field border border-line bg-canvas px-3.5 py-3 text-[15px] text-ink placeholder:text-subtle outline-none transition-colors focus:border-brand focus:bg-surface focus:ring-2 focus:ring-brand/20'

  return (
    <div className='min-h-screen bg-canvas font-sans flex items-center justify-center px-4 py-12'>
      <div className='w-full max-w-[420px]'>
        <div className='flex items-center justify-center gap-3'>
          <i className='pi pi-user text-2xl'/>
          <span className='font-semibold text-ink text-[16px]'>Content Studio</span>
        </div>

        <div className='mt-7 rounded-card border border-line bg-surface p-6 sm:p-8 shadow-[0_1px_2px_rgba(17,20,24,0.04)]'>
          <h1 className='text-[24px] sm:text-[26px] font-bold leading-[1.2] text-ink'>
            Welcome back
          </h1>
          <p className='mt-2 text-[14px] leading-[1.45] text-muted'>
            Sign in to pick up your threads and drafts.
          </p>

          {error && (
            <p className='mt-4 rounded-field border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700'>
              {error}
            </p>
          )}

          <form onSubmit={handleSubmit} className='mt-6 flex flex-col gap-4'>
            <label className='flex flex-col gap-1.5'>
              <span className='text-[13px] font-medium text-ink'>Email</span>
              <input
                type='email'
                value={form.email}
                onChange={update('email')}
                placeholder='you@company.com'
                className={fieldClass}
              />
            </label>

            <label className='flex flex-col gap-1.5'>
              <span className='text-[13px] font-medium text-ink'>Password</span>
              <input
                type='password'
                value={form.password}
                onChange={update('password')}
                placeholder='••••••••'
                className={fieldClass}
              />
            </label>

            <button
              type='submit'
              className='mt-1 w-full rounded-field bg-brand px-5 py-3 text-[14px] font-semibold text-white transition-colors hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand'
            >
              Sign in
            </button>
          </form>
        </div>

        <p className='mt-5 text-center text-[13px] text-subtle'>
          No account? <a href='#' className='text-brand hover:underline'>Create one</a>
        </p>
      </div>
    </div>
  )
}

export default Login
