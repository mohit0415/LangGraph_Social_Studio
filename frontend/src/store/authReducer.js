/**
 * Auth state is the Azure connection the user signed in with — minus the key.
 *
 * The API key is posted once to /auth/login and lives only in the backend's
 * memory. Nothing here is a secret, which is what makes it safe for this slice
 * to be the one redux-persist writes to localStorage.
 */

const initialState = {
  connection: null,
  isAuthenticated: false,
}

export const AUTH_LOGIN = 'AUTH_LOGIN'
export const AUTH_LOGOUT = 'AUTH_LOGOUT'

export const authReducer = (state = initialState, action) => {
  switch (action.type) {
    case AUTH_LOGIN:
      return { connection: action.payload, isAuthenticated: true }

    case AUTH_LOGOUT:
      return initialState

    default:
      return state
  }
}
