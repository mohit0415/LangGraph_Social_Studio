const baseURL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

export const askURL = baseURL + '/ask'
export const platformsURL = baseURL + '/platforms'
export const healthURL = baseURL + '/health'

export const threadsURL = baseURL + '/threads'
export const threadURL = (id) => `${baseURL}/threads/${encodeURIComponent(id)}`
