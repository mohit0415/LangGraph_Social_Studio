import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Provider } from 'react-redux'
import { PersistGate } from 'redux-persist/integration/react'
import 'primeicons/primeicons.css'
import './index.css'
import App from './App.jsx'
import { store, persistor } from './store/index.js'
import { AUTH_LOGOUT } from './store/authReducer.js'
import { setUnauthorizedHandler } from './utils/session.js'

// Any 401 from the API means the backend no longer holds this session's Azure
// credentials. Clear the local auth state so ProtectedRoute sends the user to
// the login page to enter them again.
setUnauthorizedHandler(() => store.dispatch({ type: AUTH_LOGOUT }))

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Provider store={store}>
      <PersistGate loading={null} persistor={persistor}>
        <App />
      </PersistGate>
    </Provider>
  </StrictMode>,
)
