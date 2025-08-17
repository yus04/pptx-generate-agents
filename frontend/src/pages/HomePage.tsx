import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  LinearProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Grid,
} from '@mui/material';
import { Add as AddIcon, PlayArrow as PlayIcon } from '@mui/icons-material';
import { useIsAuthenticated } from '@azure/msal-react';

import { SlideGenerationRequest, SlideAgenda } from '../types';
import ProgressAnimation from '../components/ProgressAnimation';
import { useSlideGeneration } from '../hooks/useSlideGeneration';
import { useUserData } from '../hooks/useUserData';

const HomePage: React.FC = () => {
  const isAuthenticated = useIsAuthenticated();
  
  // Use custom hooks
  const {
    currentJob,
    isGenerating,
    error: generationError,
    generateSlides,
    approveAgenda,
    setError: setGenerationError,
  } = useSlideGeneration();

  const {
    templates,
    promptTemplates,
    llmConfigs,
    userSettings,
    loading: dataLoading,
    error: dataError,
  } = useUserData();
  
  // Form state
  const [prompt, setPrompt] = useState('');
  const [referenceUrls, setReferenceUrls] = useState<string[]>(['']);
  const [templateId, setTemplateId] = useState('');
  const [llmConfigId, setLlmConfigId] = useState('');
  const [maxSlides, setMaxSlides] = useState(10);
  const [autoApproval, setAutoApproval] = useState(false);
  const [includeImages, setIncludeImages] = useState(true);
  const [includeTables, setIncludeTables] = useState(true);
  
  // Agenda approval
  const [agendaDialog, setAgendaDialog] = useState(false);
  const [pendingAgenda, setPendingAgenda] = useState<SlideAgenda | null>(null);

  // Set default values from user settings
  React.useEffect(() => {
    if (userSettings) {
      setAutoApproval(userSettings.auto_approval);
      if (userSettings.default_template_id) {
        setTemplateId(userSettings.default_template_id);
      }
      if (userSettings.default_llm_config_id) {
        setLlmConfigId(userSettings.default_llm_config_id);
      }
    }
  }, [userSettings]);

  // Monitor job status for agenda approval
  React.useEffect(() => {
    if (currentJob?.status === 'agenda_approval' && currentJob.agenda && !autoApproval) {
      setPendingAgenda(currentJob.agenda);
      setAgendaDialog(true);
    }
  }, [currentJob, autoApproval]);

  const error = generationError || dataError;

  const handleAddUrl = () => {
    setReferenceUrls([...referenceUrls, '']);
  };

  const handleUrlChange = (index: number, value: string) => {
    const newUrls = [...referenceUrls];
    newUrls[index] = value;
    setReferenceUrls(newUrls);
  };

  const handleRemoveUrl = (index: number) => {
    if (referenceUrls.length > 1) {
      const newUrls = referenceUrls.filter((_, i) => i !== index);
      setReferenceUrls(newUrls);
    }
  };

  const handleGenerate = async () => {
    if (!isAuthenticated) {
      setGenerationError('ログインが必要です');
      return;
    }

    if (!prompt.trim()) {
      setGenerationError('プロンプトを入力してください');
      return;
    }

    const request: SlideGenerationRequest = {
      prompt: prompt.trim(),
      reference_urls: referenceUrls.filter(url => url.trim()),
      slide_template_id: templateId || undefined,
      llm_config_id: llmConfigId || undefined,
      max_slides: maxSlides,
      auto_approval: autoApproval,
      include_images: includeImages,
      include_tables: includeTables,
    };

    try {
      await generateSlides(request);
    } catch (error) {
      // Error is handled by the hook
    }
  };

  const handleApproveAgenda = async () => {
    if (!currentJob) return;
    
    setAgendaDialog(false);
    await approveAgenda(currentJob.id, true, pendingAgenda);
  };

  const handleRejectAgenda = async () => {
    if (!currentJob) return;
    
    setAgendaDialog(false);
    await approveAgenda(currentJob.id, false);
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        PowerPoint スライド生成
      </Typography>

      {isGenerating && currentJob && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            生成中...
          </Typography>
          <LinearProgress 
            variant="determinate" 
            value={currentJob.progress} 
            sx={{ mb: 2 }}
          />
          <Typography variant="body2" color="text.secondary">
            {currentJob.current_step}
          </Typography>
          <ProgressAnimation />
        </Paper>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Paper sx={{ p: 3 }}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="生成プロンプト"
              multiline
              rows={4}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="どのようなスライドを生成したいか詳しく説明してください..."
              disabled={!isAuthenticated}
            />
          </Grid>

          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom>
              参照URL
            </Typography>
            {referenceUrls.map((url, index) => (
              <Box key={index} sx={{ display: 'flex', gap: 1, mb: 1 }}>
                <TextField
                  fullWidth
                  label={`URL ${index + 1}`}
                  value={url}
                  onChange={(e) => handleUrlChange(index, e.target.value)}
                  placeholder="https://learn.microsoft.com/..."
                  disabled={!isAuthenticated}
                />
                {referenceUrls.length > 1 && (
                  <Button
                    variant="outlined"
                    color="error"
                    onClick={() => handleRemoveUrl(index)}
                    disabled={!isAuthenticated}
                  >
                    削除
                  </Button>
                )}
              </Box>
            ))}
            <Button
              startIcon={<AddIcon />}
              onClick={handleAddUrl}
              disabled={!isAuthenticated}
            >
              URLを追加
            </Button>
          </Grid>

          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>スライドテンプレート</InputLabel>
              <Select
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                disabled={!isAuthenticated}
              >
                <MenuItem value="">デフォルト</MenuItem>
                {templates.map((template) => (
                  <MenuItem key={template.id} value={template.id}>
                    {template.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>LLMモデル</InputLabel>
              <Select
                value={llmConfigId}
                onChange={(e) => setLlmConfigId(e.target.value)}
                disabled={!isAuthenticated}
              >
                <MenuItem value="">デフォルト (GPT-4)</MenuItem>
                {llmConfigs.map((config) => (
                  <MenuItem key={config.id} value={config.id}>
                    {config.name} ({config.model_name})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              type="number"
              label="最大スライド数"
              value={maxSlides}
              onChange={(e) => setMaxSlides(Number(e.target.value))}
              inputProps={{ min: 1, max: 50 }}
              disabled={!isAuthenticated}
            />
          </Grid>

          <Grid item xs={12} md={8}>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={autoApproval}
                    onChange={(e) => setAutoApproval(e.target.checked)}
                    disabled={!isAuthenticated}
                  />
                }
                label="自動承認"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={includeImages}
                    onChange={(e) => setIncludeImages(e.target.checked)}
                    disabled={!isAuthenticated}
                  />
                }
                label="画像を含める"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={includeTables}
                    onChange={(e) => setIncludeTables(e.target.checked)}
                    disabled={!isAuthenticated}
                  />
                }
                label="テーブルを含める"
              />
            </Box>
          </Grid>

          <Grid item xs={12}>
            <Button
              variant="contained"
              size="large"
              startIcon={<PlayIcon />}
              onClick={handleGenerate}
              disabled={!isAuthenticated || isGenerating || !prompt.trim()}
              fullWidth
            >
              スライドを生成
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Agenda Approval Dialog */}
      <Dialog open={agendaDialog} maxWidth="md" fullWidth>
        <DialogTitle>アジェンダの確認</DialogTitle>
        <DialogContent>
          {pendingAgenda && (
            <Box>
              <Typography variant="body1" gutterBottom>
                以下のアジェンダでスライドを生成します。内容を確認してください。
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                推定時間: {pendingAgenda.estimated_duration}分
              </Typography>
              
              {pendingAgenda.slides.map((slide, index) => (
                <Paper key={index} sx={{ p: 2, mb: 2 }}>
                  <Typography variant="h6">
                    {slide.page_number}. {slide.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {slide.content}
                  </Typography>
                </Paper>
              ))}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleRejectAgenda} color="error">
            キャンセル
          </Button>
          <Button onClick={handleApproveAgenda} variant="contained">
            承認して続行
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default HomePage;