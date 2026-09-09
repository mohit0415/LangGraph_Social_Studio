const initialState = {
  user: null,
  isAuthenticated: false,
}

export const AUTH_LOGIN = 'AUTH_LOGIN'
export const AUTH_LOGOUT = 'AUTH_LOGOUT'

export const authReducer = (state = initialState, action) => {
  switch (action.type) {
    case AUTH_LOGIN:
      return { user: action.payload, isAuthenticated: true }

    case AUTH_LOGOUT:
      return initialState

    default:
      return state
  }
}
