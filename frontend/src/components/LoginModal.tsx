import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
} from '@mui/material';
import { useMsal } from '@azure/msal-react';
import { loginRequest } from '../config/authConfig';

interface LoginModalProps {
  open: boolean;
}

const LoginModal: React.FC<LoginModalProps> = ({ open }) => {
  const { instance } = useMsal();

  const handleLogin = () => {
    instance.loginRedirect(loginRequest);
  };

  return (
    <Dialog open={open} maxWidth="sm" fullWidth>
      <DialogTitle>ログインが必要です</DialogTitle>
      <DialogContent>
        <Box sx={{ textAlign: 'center', py: 2 }}>
          <Typography variant="body1" gutterBottom>
            PowerPointスライドを生成するには、Entra ID でログインしてください。
          </Typography>
          <Typography variant="body2" color="text.secondary">
            ログイン後、以下の機能をご利用いただけます：
          </Typography>
          <Box component="ul" sx={{ textAlign: 'left', mt: 2 }}>
            <li>カスタムプロンプトでのスライド生成</li>
            <li>スライドテンプレートの管理</li>
            <li>LLMモデルの設定</li>
            <li>生成履歴の確認</li>
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button
          onClick={handleLogin}
          variant="contained"
          fullWidth
          size="large"
        >
          Entra ID でログイン
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default LoginModal;