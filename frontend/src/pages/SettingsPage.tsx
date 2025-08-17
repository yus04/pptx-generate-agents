import React, { useState } from 'react';
import {
  Box,
  Typography,
  Tabs,
  Tab,
  Paper,
  TextField,
  Button,
  FormControlLabel,
  Switch,
  Grid,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  CircularProgress,
} from '@mui/material';
import { 
  Delete as DeleteIcon, 
  Edit as EditIcon, 
  Add as AddIcon,
  Upload as UploadIcon 
} from '@mui/icons-material';

import { useUserData } from '../hooks/useUserData';
import { PromptTemplate, LLMConfig } from '../types';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`settings-tabpanel-${index}`}
      aria-labelledby={`settings-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

const SettingsPage: React.FC = () => {
  const [currentTab, setCurrentTab] = useState(0);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogType, setDialogType] = useState<'prompt' | 'llm' | 'template'>('prompt');
  const [editingItem, setEditingItem] = useState<any>(null);

  const {
    templates,
    promptTemplates,
    llmConfigs,
    userSettings,
    loading,
    error,
    uploadTemplate,
    createPromptTemplate,
    updatePromptTemplate,
    deletePromptTemplate,
    createLLMConfig,
    updateLLMConfig,
    deleteLLMConfig,
    updateUserSettings,
    setError,
  } = useUserData();

  // Form states
  const [promptForm, setPromptForm] = useState({
    name: '',
    prompt: '',
    description: '',
    is_default: false,
  });

  const [llmForm, setLlmForm] = useState({
    name: '',
    provider: 'azure_openai' as const,
    model_name: '',
    temperature: 0.7,
    max_tokens: 2000,
    is_default: false,
  });

  const [templateFile, setTemplateFile] = useState<File | null>(null);
  const [templateForm, setTemplateForm] = useState({
    name: '',
    description: '',
  });

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
  };

  const openDialog = (type: 'prompt' | 'llm' | 'template', item?: any) => {
    setDialogType(type);
    setEditingItem(item);
    
    if (type === 'prompt') {
      setPromptForm(item || {
        name: '',
        prompt: '',
        description: '',
        is_default: false,
      });
    } else if (type === 'llm') {
      setLlmForm(item || {
        name: '',
        provider: 'azure_openai' as const,
        model_name: '',
        temperature: 0.7,
        max_tokens: 2000,
        is_default: false,
      });
    } else {
      setTemplateForm({
        name: '',
        description: '',
      });
      setTemplateFile(null);
    }
    
    setDialogOpen(true);
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setEditingItem(null);
  };

  const handleSave = async () => {
    try {
      if (dialogType === 'prompt') {
        if (editingItem) {
          await updatePromptTemplate(editingItem.id, promptForm);
        } else {
          await createPromptTemplate(promptForm);
        }
      } else if (dialogType === 'llm') {
        if (editingItem) {
          await updateLLMConfig(editingItem.id, llmForm);
        } else {
          await createLLMConfig(llmForm);
        }
      } else if (dialogType === 'template' && templateFile) {
        await uploadTemplate(templateFile, templateForm.name, templateForm.description);
      }
      
      closeDialog();
    } catch (error) {
      // Error handled by hook
    }
  };

  const handleDelete = async (type: 'prompt' | 'llm' | 'template', id: string) => {
    try {
      if (type === 'prompt') {
        await deletePromptTemplate(id);
      } else if (type === 'llm') {
        await deleteLLMConfig(id);
      }
      // Template deletion would be similar
    } catch (error) {
      // Error handled by hook
    }
  };

  const handleUserSettingsChange = async (field: string, value: any) => {
    try {
      await updateUserSettings({ [field]: value });
    } catch (error) {
      // Error handled by hook
    }
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
      <Typography variant="h4" gutterBottom>
        設定
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Paper sx={{ width: '100%' }}>
        <Tabs value={currentTab} onChange={handleTabChange}>
          <Tab label="プロンプトテンプレート" />
          <Tab label="LLM設定" />
          <Tab label="スライドテンプレート" />
          <Tab label="一般設定" />
        </Tabs>

        {/* Prompt Templates Tab */}
        <TabPanel value={currentTab} index={0}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">プロンプトテンプレート</Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => openDialog('prompt')}
            >
              新規作成
            </Button>
          </Box>
          
          <List>
            {promptTemplates.map((template) => (
              <ListItem key={template.id} divider>
                <ListItemText
                  primary={template.name}
                  secondary={template.description}
                />
                <ListItemSecondaryAction>
                  <IconButton
                    edge="end"
                    onClick={() => openDialog('prompt', template)}
                    sx={{ mr: 1 }}
                  >
                    <EditIcon />
                  </IconButton>
                  <IconButton
                    edge="end"
                    onClick={() => handleDelete('prompt', template.id)}
                  >
                    <DeleteIcon />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        </TabPanel>

        {/* LLM Configs Tab */}
        <TabPanel value={currentTab} index={1}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">LLM設定</Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => openDialog('llm')}
            >
              新規作成
            </Button>
          </Box>
          
          <List>
            {llmConfigs.map((config) => (
              <ListItem key={config.id} divider>
                <ListItemText
                  primary={config.name}
                  secondary={`${config.provider} - ${config.model_name}`}
                />
                <ListItemSecondaryAction>
                  <IconButton
                    edge="end"
                    onClick={() => openDialog('llm', config)}
                    sx={{ mr: 1 }}
                  >
                    <EditIcon />
                  </IconButton>
                  <IconButton
                    edge="end"
                    onClick={() => handleDelete('llm', config.id)}
                  >
                    <DeleteIcon />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        </TabPanel>

        {/* Templates Tab */}
        <TabPanel value={currentTab} index={2}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">スライドテンプレート</Typography>
            <Button
              variant="contained"
              startIcon={<UploadIcon />}
              onClick={() => openDialog('template')}
            >
              アップロード
            </Button>
          </Box>
          
          <List>
            {templates.map((template) => (
              <ListItem key={template.id} divider>
                <ListItemText
                  primary={template.name}
                  secondary={template.description}
                />
                <ListItemSecondaryAction>
                  <IconButton edge="end">
                    <DeleteIcon />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        </TabPanel>

        {/* General Settings Tab */}
        <TabPanel value={currentTab} index={3}>
          <Typography variant="h6" gutterBottom>
            一般設定
          </Typography>
          
          {userSettings && (
            <Grid container spacing={3}>
              <Grid item xs={12}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={userSettings.auto_approval}
                      onChange={(e) => handleUserSettingsChange('auto_approval', e.target.checked)}
                    />
                  }
                  label="アジェンダの自動承認"
                />
              </Grid>
              <Grid item xs={12}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={userSettings.notification_enabled}
                      onChange={(e) => handleUserSettingsChange('notification_enabled', e.target.checked)}
                    />
                  }
                  label="通知を有効にする"
                />
              </Grid>
            </Grid>
          )}
        </TabPanel>
      </Paper>

      {/* Dialog for creating/editing items */}
      <Dialog open={dialogOpen} onClose={closeDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingItem ? '編集' : '新規作成'} - {
            dialogType === 'prompt' ? 'プロンプトテンプレート' :
            dialogType === 'llm' ? 'LLM設定' : 'スライドテンプレート'
          }
        </DialogTitle>
        <DialogContent>
          {dialogType === 'prompt' && (
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="名前"
                  value={promptForm.name}
                  onChange={(e) => setPromptForm({ ...promptForm, name: e.target.value })}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  multiline
                  rows={4}
                  label="プロンプト"
                  value={promptForm.prompt}
                  onChange={(e) => setPromptForm({ ...promptForm, prompt: e.target.value })}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="説明"
                  value={promptForm.description}
                  onChange={(e) => setPromptForm({ ...promptForm, description: e.target.value })}
                />
              </Grid>
            </Grid>
          )}
          
          {dialogType === 'template' && (
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <input
                  type="file"
                  accept=".pptx"
                  onChange={(e) => setTemplateFile(e.target.files?.[0] || null)}
                  style={{ marginBottom: '16px' }}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="名前"
                  value={templateForm.name}
                  onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="説明"
                  value={templateForm.description}
                  onChange={(e) => setTemplateForm({ ...templateForm, description: e.target.value })}
                />
              </Grid>
            </Grid>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeDialog}>キャンセル</Button>
          <Button onClick={handleSave} variant="contained">
            保存
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SettingsPage;