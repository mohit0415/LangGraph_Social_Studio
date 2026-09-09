/**
 * The signed-in session id.
 *
 * This is the only thing the browser holds after login. The Azure API key is
 * posted once to /auth/login and never comes back — it lives in the backend's
 * memory for the life of the session, so it is never in localStorage, never in
 * redux, and never re-sent on later requests.
 */

const STORAGE_KEY = 'studio.sessionId'

const read = () => {
  try {
    return window.localStorage.getItem(STORAGE_KEY) || null
  } catch {
    return null
  }
}

let sessionId = read()

let onUnauthorized = () => {}

export const SESSION_HEADER = 'X-Session-Id'

export const getSessionId = () => sessionId

export const setSessionId = (id) => {
  sessionId = id || null
  try {
    if (sessionId) window.localStorage.setItem(STORAGE_KEY, sessionId)
    else window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Private mode or blocked storage: the id still works for this tab.
  }
}

export const clearSessionId = () => setSessionId(null)

export const sessionHeaders = () =>
  sessionId ? { [SESSION_HEADER]: sessionId } : {}

/**
 * Registered once at startup. Called when any request comes back 401, so an
 * expired or forgotten backend session drops the user on the login page
 * instead of failing silently on their next action.
 */
export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = typeof fn === 'function' ? fn : () => {}
}

export const handleUnauthorized = () => {
  clearSessionId()
  onUnauthorized()
}
