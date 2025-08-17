import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Container } from '@mui/material';
import { useIsAuthenticated } from '@azure/msal-react';

import Navbar from './components/Navbar';
import HomePage from './pages/HomePage';
import SettingsPage from './pages/SettingsPage';
import HistoryPage from './pages/HistoryPage';
import LoginModal from './components/LoginModal';

function App() {
  const isAuthenticated = useIsAuthenticated();

  return (
    <div className="App">
      <Navbar />
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </Container>
      {!isAuthenticated && <LoginModal open={true} />}
    </div>
  );
}

export default App;