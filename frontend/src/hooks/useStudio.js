import { useCallback, useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'

import {
  askStudio,
  deleteThread,
  fetchPlatforms,
  fetchThread,
  fetchThreads,
} from '../utils/studio_api'
import {
  THREAD_START,
  THREAD_SAVE,
  THREAD_CLARIFY,
  THREAD_ERROR,
  THREAD_SELECT,
  THREAD_NEW_SOURCE,
  THREAD_EXPIRED,
  THREAD_DISMISS,
  THREAD_REMOVE,
  THREADS_LOADED,
  THREAD_LOADING,
  THREAD_LOADED,
} from '../store/threadsReducer'

export const useStudio = () => {
  const dispatch = useDispatch()
  const { byId, order, activeId, status, error, clarify, listLoaded } = useSelector(
    (s) => s.threads,
  )

  const [limits, setLimits] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetchPlatforms().then((list) => {
      if (cancelled || !list) return
      setLimits(Object.fromEntries(list.map((p) => [p.id, p.max_chars])))
    })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchThreads().then((res) => {
      if (cancelled) return
      if (!res.ok) {
        dispatch({ type: THREAD_ERROR, payload: res.error })
        return
      }
      dispatch({ type: THREADS_LOADED, payload: res.data })
    })
    return () => {
      cancelled = true
    }
  }, [dispatch])

  const threads = order.map((id) => byId[id]).filter(Boolean)
  const activeThread = activeId ? byId[activeId] : null

  const selectThread = useCallback(
    async (id) => {
      dispatch({ type: THREAD_SELECT, payload: id })
      if (byId[id]?.loaded) return

      dispatch({ type: THREAD_LOADING })
      const res = await fetchThread(id)

      if (!res.ok) {
        if (/unknown|not found/i.test(res.error)) {
          dispatch({ type: THREAD_EXPIRED, payload: id })
        } else {
          dispatch({ type: THREAD_ERROR, payload: res.error })
        }
        return
      }

      dispatch({ type: THREAD_LOADED, payload: { data: res.data } })
    },
    [byId, dispatch],
  )

  const send = async (query, { threadId = null } = {}) => {
    dispatch({
      type: THREAD_START,
      payload: { mode: threadId ? 'refining' : 'generating' },
    })

    const res = await askStudio({ query, threadId })

    if (!res.ok) {
      if (threadId && /expired|unknown/i.test(res.error)) {
        dispatch({ type: THREAD_EXPIRED, payload: threadId })
      } else {
        dispatch({ type: THREAD_ERROR, payload: res.error })
      }
      return
    }

    if (res.data.action === 'clarify') {
      dispatch({ type: THREAD_CLARIFY, payload: res.data })
      return
    }

    dispatch({ type: THREAD_SAVE, payload: { data: res.data, query } })
  }

  const removeThread = async (id) => {
    dispatch({ type: THREAD_REMOVE, payload: id })
    const res = await deleteThread(id)
    if (!res.ok) {
      dispatch({ type: THREAD_ERROR, payload: res.error })
      const list = await fetchThreads()
      if (list.ok) dispatch({ type: THREADS_LOADED, payload: list.data })
    }
  }

  return {
    threads,
    activeThread,
    activeId,
    status,
    error,
    clarify,
    limits,
    listLoaded,
    isGenerating: status === 'generating',
    isRefining: status === 'refining',
    isLoadingThread: status === 'loading',

    generate: (query) => send(query),
    followUp: (query) => send(query, { threadId: activeId }),
    selectThread,
    newSource: () => dispatch({ type: THREAD_NEW_SOURCE }),
    dismissClarify: () => dispatch({ type: THREAD_DISMISS }),
    removeThread,
  }
}
