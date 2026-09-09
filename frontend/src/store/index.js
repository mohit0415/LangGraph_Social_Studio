import { legacy_createStore as createStore, combineReducers } from "redux";
import { persistStore, persistReducer } from "redux-persist";
import createWebStorage from "redux-persist/es/storage/createWebStorage";

import { loaderReducer } from "./loaderReducer";
import { threadsReducer } from "./threadsReducer";
import { authReducer } from "./authReducer";

const storage = createWebStorage("local");

const rootReducer = combineReducers({
  loader: loaderReducer,
  threads: threadsReducer,
  auth: authReducer,
});

const rootPersistConfig = {
  key: "root",
  storage,
  whitelist: ["auth"],
};

const persistedReducer = persistReducer(rootPersistConfig, rootReducer);

export const store = createStore(persistedReducer);
export const persistor = persistStore(store);
