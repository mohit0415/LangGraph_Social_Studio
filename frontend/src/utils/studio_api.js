import {
  postWithoutHeaders,
  getWithoutHeaders,
  deleteWithoutHeaders,
} from './network_utils'
import { clearSessionId, setSessionId } from './session'
import {
  askURL,
  loginURL,
  logoutURL,
  platformsURL,
  sessionURL,
  threadsURL,
  threadURL,
} from './url_constants'

const UNREACHABLE = 'Cannot reach the studio backend. Is it running on port 8000?'

const unwrap = (res) => {
  if (!res) return { ok: false, error: UNREACHABLE }
  if (!res.ok) {
    return {
      ok: false,
      status: res.status,
      error: res.data?.detail || `Request failed (${res.status})`,
    }
  }
  return { ok: true, data: res.data }
}

/**
 * Post the Azure credentials once. The backend verifies them against Azure,
 * keeps them in memory, and returns a session id — the key itself is never
 * stored here and never comes back in the response.
 */
export const loginWithAzure = async ({
  endpoint,
  apiKey,
  deployment,
  apiVersion,
  simpleDeployment,
}) => {
  const res = unwrap(
    await postWithoutHeaders(
      loginURL,
      {
        endpoint,
        api_key: apiKey,
        deployment,
        api_version: apiVersion,
        simple_deployment: simpleDeployment || '',
      },
      { signalExpiry: false },
    ),
  )

  if (!res.ok) return res

  setSessionId(res.data.session_id)
  return res
}

export const logoutStudio = async () => {
  const res = await postWithoutHeaders(logoutURL, {}, { signalExpiry: false })
  clearSessionId()
  return unwrap(res)
}

/** Is the stored session id still live on the backend? */
export const fetchSession = async () => {
  const res = unwrap(await getWithoutHeaders(sessionURL, { signalExpiry: false }))
  if (!res.ok) return { ok: false, authenticated: false, error: res.error }
  return { ok: true, authenticated: Boolean(res.data?.authenticated), data: res.data }
}

export const askStudio = async ({ query, threadId = null }) => {
  const body = threadId ? { query, thread_id: threadId } : { query }
  return unwrap(await postWithoutHeaders(askURL, body))
}

export const fetchThreads = async () => {
  const res = unwrap(await getWithoutHeaders(threadsURL))
  if (!res.ok) return res

  return {
    ok: true,
    data: res.data.threads.map((t) => ({
      id: t.thread_id,
      title: t.title,
      createdAt: t.created_at * 1000,
      updatedAt: t.updated_at * 1000,
      messageCount: t.message_count,
    })),
  }
}

export const fetchThread = async (id) => unwrap(await getWithoutHeaders(threadURL(id)))

export const deleteThread = async (id) => unwrap(await deleteWithoutHeaders(threadURL(id)))

export const fetchPlatforms = async () => {
  const res = await getWithoutHeaders(platformsURL)
  if (!res?.ok) return null
  return res.data.platforms
}
