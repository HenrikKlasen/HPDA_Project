import { useSelector, useDispatch } from 'react-redux';
import { selectAllFiles, selectSingleFile } from '../redux/ParticipantStatusFileSlice';

export function ActivityLogFiles() {
  const dispatch = useDispatch();
  const allFiles = useSelector(selectAllFiles);
  const selectedId = useSelector((state) => state.files.selectedFileId);

  return (
    <div className="file-sidebar">
      <h3>Available CSV Files</h3>
      <ul>
        {allFiles.map((file) => (
          <li 
            key={file.name}
            style={{ 
              fontWeight: file.name === selectedId ? 'bold' : 'normal',
              cursor: 'pointer',
              color: file.name === selectedId ? 'blue' : 'black'
            }}
            onClick={() => dispatch(selectSingleFile(file.name))}
          >
            {file.name}
          </li>
        ))}
      </ul>
    </div>
  );
}