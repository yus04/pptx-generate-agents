import React, { useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import { Container } from '@mui/material';
import { useIsAuthenticated, useMsal } from '@azure/msal-react';

import Navbar from './components/Navbar';
import HomePage from './pages/HomePage';
import SettingsPage from './pages/SettingsPage';
import HistoryPage from './pages/HistoryPage';
import LoginModal from './components/LoginModal';

function App() {
  const isAuthenticated = useIsAuthenticated();
  const { instance } = useMsal();

  useEffect(() => {
    const handleRedirectPromise = async () => {
      try {
        console.log('Checking for redirect response...');
        const response = await instance.handleRedirectPromise();
        if (response) {
          console.log('Redirect response received:', response);
          instance.setActiveAccount(response.account);
        }
        
        // Check if there are any accounts available
        const accounts = instance.getAllAccounts();
        console.log('Available accounts after redirect check:', accounts);
        
        if (accounts.length > 0 && !instance.getActiveAccount()) {
          // Set the first account as the active account
          instance.setActiveAccount(accounts[0]);
          console.log('Active account set to:', accounts[0].username);
        }
      } catch (redirectError) {
        console.error('Error handling redirect promise:', redirectError);
        // Handle specific redirect errors
        if (redirectError instanceof Error && 
            (redirectError.message.includes('invalid_resource') || 
             redirectError.message.includes('AADSTS500011'))) {
          console.warn('Clearing cache due to invalid resource error');
          await instance.clearCache();
        }
      }
    };

    handleRedirectPromise();
  }, [instance]);

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