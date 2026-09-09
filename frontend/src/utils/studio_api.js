import {
  postWithoutHeaders,
  getWithoutHeaders,
  deleteWithoutHeaders,
} from './network_utils'
import { askURL, platformsURL, threadsURL, threadURL } from './url_constants'

const UNREACHABLE = 'Cannot reach the studio backend. Is it running on port 8000?'

const unwrap = (res) => {
  if (!res) return { ok: false, error: UNREACHABLE }
  if (!res.ok) {
    return { ok: false, error: res.data?.detail || `Request failed (${res.status})` }
  }
  return { ok: true, data: res.data }
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
