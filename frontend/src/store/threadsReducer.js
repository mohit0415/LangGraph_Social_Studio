const initialState = {
  byId: {},
  order: [],
  activeId: null,
  status: 'idle',
  error: null,
  clarify: null,
  listLoaded: false,
}

export const THREAD_START = 'THREAD_START'
export const THREAD_SAVE = 'THREAD_SAVE'
export const THREAD_CLARIFY = 'THREAD_CLARIFY'
export const THREAD_ERROR = 'THREAD_ERROR'
export const THREAD_SELECT = 'THREAD_SELECT'
export const THREAD_NEW_SOURCE = 'THREAD_NEW_SOURCE'
export const THREAD_EXPIRED = 'THREAD_EXPIRED'
export const THREAD_DISMISS = 'THREAD_DISMISS'
export const THREAD_REMOVE = 'THREAD_REMOVE'

export const THREADS_LOADED = 'THREADS_LOADED'
export const THREAD_LOADING = 'THREAD_LOADING'
export const THREAD_LOADED = 'THREAD_LOADED'

const omit = (map, key) =>
  Object.fromEntries(Object.entries(map).filter(([id]) => id !== key))

const contentFrom = (data) => ({
  brief: data.brief,
  posts: data.posts,
  trace: data.trace,
  events: data.events || [],
  messages: data.messages || [],
  loaded: true,
})

export const threadsReducer = (state = initialState, action) => {
  switch (action.type) {
    case THREADS_LOADED: {
      const byId = {}
      const order = []

      for (const row of action.payload) {
        order.push(row.id)
        byId[row.id] = { ...state.byId[row.id], ...row, loaded: state.byId[row.id]?.loaded ?? false }
      }

      return {
        ...state,
        byId,
        order,
        listLoaded: true,
        activeId: byId[state.activeId] ? state.activeId : null,
      }
    }

    case THREAD_LOADING:
      return { ...state, status: 'loading', error: null, clarify: null }

    case THREAD_LOADED: {
      const { data } = action.payload
      const id = data.thread_id
      return {
        ...state,
        status: 'idle',
        error: null,
        activeId: id,
        byId: {
          ...state.byId,
          [id]: { ...state.byId[id], id, ...contentFrom(data) },
        },
      }
    }

    case THREAD_START:
      return {
        ...state,
        status: action.payload.mode,
        error: null,
        clarify: null,
      }

    case THREAD_SAVE: {
      const { data, query } = action.payload
      const id = data.thread_id
      const existing = state.byId[id]

      return {
        ...state,
        status: 'idle',
        error: null,
        clarify: null,
        activeId: id,
        order: state.order.includes(id) ? state.order : [id, ...state.order],
        byId: {
          ...state.byId,
          [id]: {
            id,
            title: existing?.title || query,
            createdAt: existing?.createdAt || Date.now(),
            updatedAt: Date.now(),
            ...contentFrom(data),
          },
        },
      }
    }

    case THREAD_CLARIFY:
      return {
        ...state,
        status: 'idle',
        clarify: {
          message: action.payload.message,
          options: action.payload.options,
        },
      }

    case THREAD_ERROR:
      return { ...state, status: 'idle', error: action.payload, clarify: null }

    case THREAD_DISMISS:
      return { ...state, clarify: null, error: null }

    case THREAD_SELECT:
      return { ...state, activeId: action.payload, error: null, clarify: null }

    case THREAD_NEW_SOURCE:
      return { ...state, activeId: null, error: null, clarify: null }

    case THREAD_REMOVE: {
      return {
        ...state,
        byId: omit(state.byId, action.payload),
        order: state.order.filter((id) => id !== action.payload),
        activeId: state.activeId === action.payload ? null : state.activeId,
        clarify: state.activeId === action.payload ? null : state.clarify,
      }
    }

    case THREAD_EXPIRED: {
      return {
        ...state,
        status: 'idle',
        byId: omit(state.byId, action.payload),
        order: state.order.filter((id) => id !== action.payload),
        activeId: state.activeId === action.payload ? null : state.activeId,
        error: 'That thread no longer exists on the server. Start a new source.',
      }
    }

    default:
      return state
  }
}
