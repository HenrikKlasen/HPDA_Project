import { useSelector, useDispatch } from 'react-redux';
import { selectAllFiles, selectSingleFile, getSelectedFile } from '../redux/ParticipantStatusFileSlice';

import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import Select from '@mui/material/Select';

export function ActivityLogComboBox() {
  const dispatch = useDispatch();
  const allFiles = useSelector(selectAllFiles);
  const selectedFile = useSelector(getSelectedFile);

  const file_items = allFiles.map((file) => (
          <MenuItem value={file.name}>
            {file.name}
          </MenuItem>
        ));

  const handleChange = (event) => {
    dispatch(selectSingleFile(event.target.value));
  };

  return (
    <FormControl sx={{ m: 1, minWidth: 320 }}>
        <InputLabel id="selection-of-participant">Participant</InputLabel>
        <Select
            labelId="selection-of-participant-label"
            id="selection-of-participant"
            label="Participant Status Log"
            onChange={handleChange}
            value={selectedFile ? selectedFile.name : ""}
            autoWidth
        >
            {file_items}
        </Select>
    </FormControl>
  );
}