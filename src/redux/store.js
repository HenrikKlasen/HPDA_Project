import { configureStore } from '@reduxjs/toolkit'

import participantStatusReducer from './ParticipantStatusFileSlice'

export default configureStore({
  reducer: {
    participantStatusFiles: participantStatusReducer
  }
})
