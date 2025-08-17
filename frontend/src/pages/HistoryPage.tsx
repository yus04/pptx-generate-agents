import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  Chip,
  IconButton,
  Alert,
  CircularProgress,
} from '@mui/material';
import { 
  Download as DownloadIcon,
  Refresh as RefreshIcon 
} from '@mui/icons-material';

import { GenerationHistory } from '../types';
import apiService from '../services/apiService';

const HistoryPage: React.FC = () => {
  const [history, setHistory] = useState<GenerationHistory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = async () => {
    try {
      setLoading(true);
      setError(null);
      const historyData = await apiService.getGenerationHistory();
      setHistory(historyData);
    } catch (error: any) {
      setError(error.message || '履歴の読み込みに失敗しました');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const handleDownload = (url: string, title: string) => {
    // Create a temporary link to download the file
    const link = document.createElement('a');
    link.href = url;
    link.download = `${title}.pptx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('ja-JP');
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">
          生成履歴
        </Typography>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={loadHistory}
          disabled={loading}
        >
          更新
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>タイトル</TableCell>
              <TableCell align="center">スライド数</TableCell>
              <TableCell align="center">作成日時</TableCell>
              <TableCell align="center">ダウンロード</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {history.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} align="center">
                  <Typography variant="body2" color="text.secondary">
                    生成履歴がありません
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              history.map((item) => (
                <TableRow key={item.id} hover>
                  <TableCell>
                    <Typography variant="body1" fontWeight="medium">
                      {item.title}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Chip 
                      label={`${item.slide_count} ページ`} 
                      size="small" 
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell align="center">
                    <Typography variant="body2" color="text.secondary">
                      {formatDate(item.created_at)}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <IconButton
                      color="primary"
                      onClick={() => handleDownload(item.blob_url, item.title)}
                      title="ダウンロード"
                    >
                      <DownloadIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {history.length > 0 && (
        <Box mt={2}>
          <Typography variant="body2" color="text.secondary">
            合計 {history.length} 件の履歴があります
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default HistoryPage;