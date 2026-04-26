import Box from '@mui/material/Box';
import Tab from '@mui/material/Tab';
import TabContext from '@mui/lab/TabContext';
import TabList from '@mui/lab/TabList';
import TabPanel from '@mui/lab/TabPanel';
import CssBaseline from '@mui/material/CssBaseline';

import * as React from 'react';
import Home from './Home'
import Graph1 from './Graph'

function App() {
  const [tabIndex, setTabIndex] = React.useState("0")
  const handleChange = (event, newValue ) => {
    setTabIndex(newValue);
  };

  return (
    <>
      <CssBaseline />
      <TabContext value={tabIndex}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <TabList onChange={handleChange} aria-label="lab API tabs example">
            <Tab label="Home" value="0" />
            <Tab label="Graph1" value="1" />
            <Tab label="Graph2" value="2" />
          </TabList>
        </Box>
        <TabPanel value="0"><Home/></TabPanel>
        <TabPanel value="1"><Graph1/></TabPanel>
        <TabPanel value="2">Item Three</TabPanel>
      </TabContext>
    </>
  )
}

export default App
