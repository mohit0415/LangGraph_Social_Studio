import React, { useState } from 'react'
import { useDispatch } from 'react-redux'
import { useNavigate, useLocation } from 'react-router-dom'
import { AUTH_LOGIN } from '../store/authReducer'
import { loginWithAzure } from '../utils/studio_api'

const DEFAULT_API_VERSION = '2024-12-01-preview'

const EMPTY = {
  endpoint: '',
  apiKey: '',
  deployment: '',
  apiVersion: DEFAULT_API_VERSION,
  simpleDeployment: '',
}

const Login = () => {
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [showKey, setShowKey] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const dispatch = useDispatch()
  const navigate = useNavigate()
  const location = useLocation()

  const from = location.state?.from?.pathname || '/studio'

  const update = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (busy) return

    if (!form.endpoint.trim() || !form.apiKey.trim() || !form.deployment.trim()) {
      setError('Endpoint, API key and deployment are all required.')
      return
    }

    setError('')
    setBusy(true)

    const res = await loginWithAzure({
      endpoint: form.endpoint.trim(),
      apiKey: form.apiKey.trim(),
      deployment: form.deployment.trim(),
      apiVersion: form.apiVersion.trim() || DEFAULT_API_VERSION,
      simpleDeployment: form.simpleDeployment.trim(),
    })

    setBusy(false)

    if (!res.ok) {
      setError(res.error)
      return
    }

    // Only the non-secret half of the response reaches redux. The key stays in
    // the backend's session; the browser keeps just the session id.
    dispatch({
      type: AUTH_LOGIN,
      payload: {
        endpoint: res.data.endpoint,
        deployment: res.data.deployment,
        apiVersion: res.data.api_version,
        simpleDeployment: res.data.simple_deployment,
      },
    })

    setForm(EMPTY)
    navigate(from, { replace: true })
  }

  const fieldClass =
    'w-full rounded-field border border-line bg-canvas px-3.5 py-3 text-[15px] text-ink placeholder:text-subtle outline-none transition-colors focus:border-brand focus:bg-surface focus:ring-2 focus:ring-brand/20 disabled:opacity-60'

  return (
    <div className='min-h-screen bg-canvas font-sans flex items-center justify-center px-4 py-12'>
      <div className='w-full max-w-[460px]'>
        <div className='flex items-center justify-center gap-3'>
          <i className='pi pi-sparkles text-brand text-2xl' />
          <span className='font-semibold text-ink text-[16px]'>Content Studio</span>
        </div>

        <div className='mt-7 rounded-card border border-line bg-surface p-6 sm:p-8 shadow-[0_1px_2px_rgba(17,20,24,0.04)]'>
          <h1 className='text-[24px] sm:text-[26px] font-bold leading-[1.2] text-ink'>
            Connect your Azure OpenAI
          </h1>
          <p className='mt-2 text-[14px] leading-[1.45] text-muted'>
            The studio runs on your own deployment. These credentials are verified
            against Azure, then held in memory for this session only — never written
            to disk and never stored in your browser.
          </p>

          {error && (
            <p className='mt-4 rounded-field border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700'>
              {error}
            </p>
          )}

          <form onSubmit={handleSubmit} className='mt-6 flex flex-col gap-4'>
            <label className='flex flex-col gap-1.5'>
              <span className='text-[13px] font-medium text-ink'>Endpoint</span>
              <input
                type='url'
                value={form.endpoint}
                onChange={update('endpoint')}
                disabled={busy}
                autoComplete='off'
                spellCheck='false'
                placeholder='https://your-resource.openai.azure.com'
                className={fieldClass}
              />
            </label>

            <label className='flex flex-col gap-1.5'>
              <span className='text-[13px] font-medium text-ink'>API key</span>
              <div className='relative'>
                <input
                  type={showKey ? 'text' : 'password'}
                  value={form.apiKey}
                  onChange={update('apiKey')}
                  disabled={busy}
                  autoComplete='off'
                  spellCheck='false'
                  placeholder='••••••••••••••••••••••••'
                  className={`${fieldClass} pr-11`}
                />
                <button
                  type='button'
                  onClick={() => setShowKey((v) => !v)}
                  title={showKey ? 'Hide key' : 'Show key'}
                  className='absolute right-1 top-1/2 -translate-y-1/2 rounded-full p-2 text-subtle transition-colors hover:text-ink'
                >
                  <i className={`pi ${showKey ? 'pi-eye-slash' : 'pi-eye'} text-[13px]`} />
                </button>
              </div>
            </label>

            <label className='flex flex-col gap-1.5'>
              <span className='text-[13px] font-medium text-ink'>Deployment</span>
              <input
                type='text'
                value={form.deployment}
                onChange={update('deployment')}
                disabled={busy}
                autoComplete='off'
                spellCheck='false'
                placeholder='gpt-4o-mini'
                className={fieldClass}
              />
            </label>

            <label className='flex flex-col gap-1.5'>
              <span className='text-[13px] font-medium text-ink'>API version</span>
              <input
                type='text'
                value={form.apiVersion}
                onChange={update('apiVersion')}
                disabled={busy}
                autoComplete='off'
                spellCheck='false'
                placeholder={DEFAULT_API_VERSION}
                className={fieldClass}
              />
            </label>

            <button
              type='button'
              onClick={() => setShowAdvanced((v) => !v)}
              className='self-start text-[13px] text-brand hover:underline'
            >
              <i
                className={`pi ${showAdvanced ? 'pi-chevron-down' : 'pi-chevron-right'} mr-1 text-[10px]`}
              />
              Model routing (optional)
            </button>

            {showAdvanced && (
              <label className='flex flex-col gap-1.5'>
                <span className='text-[13px] font-medium text-ink'>
                  Deployment for the simple tier
                </span>
                <input
                  type='text'
                  value={form.simpleDeployment}
                  onChange={update('simpleDeployment')}
                  disabled={busy}
                  autoComplete='off'
                  spellCheck='false'
                  placeholder='leave blank to reuse the deployment above'
                  className={fieldClass}
                />
                <span className='text-[12.5px] leading-[1.45] text-subtle'>
                  Straightforward copy is routed to this cheaper deployment; briefs
                  with benchmarks, incidents or long source material still go to the
                  main one.
                </span>
              </label>
            )}

            <button
              type='submit'
              disabled={busy}
              className='mt-1 flex w-full items-center justify-center gap-2 rounded-field bg-brand px-5 py-3 text-[14px] font-semibold text-white transition-colors hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-70'
            >
              {busy && <i className='pi pi-spin pi-spinner text-[13px]' />}
              {busy ? 'Verifying with Azure…' : 'Connect'}
            </button>
          </form>
        </div>

        <p className='mt-5 text-center text-[13px] leading-[1.5] text-subtle'>
          Find these under <span className='text-muted'>Keys and Endpoint</span> and{' '}
          <span className='text-muted'>Deployments</span> in your Azure OpenAI resource.
        </p>
      </div>
    </div>
  )
}

export default Login
