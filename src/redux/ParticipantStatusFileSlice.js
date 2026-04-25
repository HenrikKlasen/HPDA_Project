import { createSlice, createEntityAdapter } from '@reduxjs/toolkit';

const csvModules = ["a.csv", "b.csv"]// import.meta.glob('../vast_assets/Datasets/Activity Logs/*.csv');

const filenames = Object.keys(csvModules).map((path) => {
  return path.split('/').pop();
});

const filesAdapter = createEntityAdapter({
  selectId: (file) => file.name,
  sortComparer: (a, b) => a.name.localeCompare(b.name),
});

const filesSlice = createSlice({
  name: 'files',
  initialState: filesAdapter.getInitialState({
    ids: filenames,
    entities: filenames.reduce((acc, name) => ({ ...acc, [name]: { name } }), {}),
    selectedFileId: null,
  }),

  reducers: {
    setFiles: filesAdapter.setAll,
    selectSingleFile: (state, action) => {
      state.selectedFileId = action.payload;
    },

    toggleFileSelection: (state, action) => {
      const id = action.payload;
      const index = state.selectedFileIds.indexOf(id);
      if (index === -1) {
        state.selectedFileIds.push(id);
      } else {
        state.selectedFileIds.splice(index, 1);
      }
    },
  },
});

export const { setFiles, selectSingleFile, toggleFileSelection } = filesSlice.actions;
export default filesSlice.reducer;