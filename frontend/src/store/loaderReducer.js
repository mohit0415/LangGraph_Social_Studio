const initialState = {
  isLoading: false,
};

export const loaderReducer = (state = initialState, action) => {
  switch (action.type) {
    case "LOADIN":
      return {
        ...state,
        isLoading: true,
      };

    case "LOADOUT":
      return {
        ...state,
        isLoading: false,
      };

    default:
      return state;
  }
};