import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Avatar,
  Menu,
  MenuItem,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useIsAuthenticated, useMsal } from '@azure/msal-react';
import { AccountInfo } from '@azure/msal-browser';

const Navbar: React.FC = () => {
  const navigate = useNavigate();
  const isAuthenticated = useIsAuthenticated();
  const { instance, accounts } = useMsal();
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

  const handleProfileMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    instance.logoutRedirect();
    handleMenuClose();
  };

  const account: AccountInfo | undefined = accounts[0];

  return (
    <AppBar position="static">
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          PowerPoint スライド自動生成
        </Typography>
        
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button color="inherit" onClick={() => navigate('/')}>
            ホーム
          </Button>
          {isAuthenticated && (
            <>
              <Button color="inherit" onClick={() => navigate('/settings')}>
                設定
              </Button>
              <Button color="inherit" onClick={() => navigate('/history')}>
                履歴
              </Button>
            </>
          )}
        </Box>

        {isAuthenticated && account && (
          <Box sx={{ ml: 2 }}>
            <Avatar
              onClick={handleProfileMenuOpen}
              sx={{ cursor: 'pointer' }}
            >
              {account.name?.charAt(0) || 'U'}
            </Avatar>
            <Menu
              anchorEl={anchorEl}
              open={Boolean(anchorEl)}
              onClose={handleMenuClose}
            >
              <MenuItem onClick={handleMenuClose}>
                {account.name || account.username}
              </MenuItem>
              <MenuItem onClick={handleLogout}>ログアウト</MenuItem>
            </Menu>
          </Box>
        )}
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;