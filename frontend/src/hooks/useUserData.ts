import { useState, useEffect } from 'react';
import apiService from '../services/apiService';
import { SlideTemplate, PromptTemplate, LLMConfig, UserSettings } from '../types';

export const useUserData = () => {
  const [templates, setTemplates] = useState<SlideTemplate[]>([]);
  const [promptTemplates, setPromptTemplates] = useState<PromptTemplate[]>([]);
  const [llmConfigs, setLlmConfigs] = useState<LLMConfig[]>([]);
  const [userSettings, setUserSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadUserData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [templatesData, promptTemplatesData, llmConfigsData, settingsData] = await Promise.all([
        apiService.getTemplates(),
        apiService.getPromptTemplates(),
        apiService.getLLMConfigs(),
        apiService.getUserSettings(),
      ]);

      setTemplates(templatesData);
      setPromptTemplates(promptTemplatesData);
      setLlmConfigs(llmConfigsData);
      setUserSettings(settingsData);
    } catch (error: any) {
      setError(error.message || 'データの読み込みに失敗しました');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUserData();
  }, []);

  // Template operations
  const uploadTemplate = async (file: File, name: string, description: string) => {
    try {
      const newTemplate = await apiService.uploadTemplate(file, name, description);
      setTemplates(prev => [...prev, newTemplate]);
      return newTemplate;
    } catch (error: any) {
      setError(error.message || 'テンプレートのアップロードに失敗しました');
      throw error;
    }
  };

  const deleteTemplate = async (templateId: string) => {
    try {
      await apiService.deleteTemplate(templateId);
      setTemplates(prev => prev.filter(t => t.id !== templateId));
    } catch (error: any) {
      setError(error.message || 'テンプレートの削除に失敗しました');
      throw error;
    }
  };

  // Prompt template operations
  const createPromptTemplate = async (template: Omit<PromptTemplate, 'id' | 'user_id' | 'created_at'>) => {
    try {
      const newTemplate = await apiService.createPromptTemplate(template);
      setPromptTemplates(prev => [...prev, newTemplate]);
      return newTemplate;
    } catch (error: any) {
      setError(error.message || 'プロンプトテンプレートの作成に失敗しました');
      throw error;
    }
  };

  const updatePromptTemplate = async (templateId: string, template: Partial<PromptTemplate>) => {
    try {
      const updatedTemplate = await apiService.updatePromptTemplate(templateId, template);
      setPromptTemplates(prev => prev.map(t => t.id === templateId ? updatedTemplate : t));
      return updatedTemplate;
    } catch (error: any) {
      setError(error.message || 'プロンプトテンプレートの更新に失敗しました');
      throw error;
    }
  };

  const deletePromptTemplate = async (templateId: string) => {
    try {
      await apiService.deletePromptTemplate(templateId);
      setPromptTemplates(prev => prev.filter(t => t.id !== templateId));
    } catch (error: any) {
      setError(error.message || 'プロンプトテンプレートの削除に失敗しました');
      throw error;
    }
  };

  // LLM config operations
  const createLLMConfig = async (config: Omit<LLMConfig, 'id' | 'user_id' | 'created_at'>) => {
    try {
      const newConfig = await apiService.createLLMConfig(config);
      setLlmConfigs(prev => [...prev, newConfig]);
      return newConfig;
    } catch (error: any) {
      setError(error.message || 'LLM設定の作成に失敗しました');
      throw error;
    }
  };

  const updateLLMConfig = async (configId: string, config: Partial<LLMConfig>) => {
    try {
      const updatedConfig = await apiService.updateLLMConfig(configId, config);
      setLlmConfigs(prev => prev.map(c => c.id === configId ? updatedConfig : c));
      return updatedConfig;
    } catch (error: any) {
      setError(error.message || 'LLM設定の更新に失敗しました');
      throw error;
    }
  };

  const deleteLLMConfig = async (configId: string) => {
    try {
      await apiService.deleteLLMConfig(configId);
      setLlmConfigs(prev => prev.filter(c => c.id !== configId));
    } catch (error: any) {
      setError(error.message || 'LLM設定の削除に失敗しました');
      throw error;
    }
  };

  // User settings operations
  const updateUserSettings = async (settings: Partial<UserSettings>) => {
    try {
      const updatedSettings = await apiService.updateUserSettings(settings);
      setUserSettings(updatedSettings);
      return updatedSettings;
    } catch (error: any) {
      setError(error.message || 'ユーザー設定の更新に失敗しました');
      throw error;
    }
  };

  return {
    // Data
    templates,
    promptTemplates,
    llmConfigs,
    userSettings,
    loading,
    error,
    
    // Operations
    loadUserData,
    uploadTemplate,
    deleteTemplate,
    createPromptTemplate,
    updatePromptTemplate,
    deletePromptTemplate,
    createLLMConfig,
    updateLLMConfig,
    deleteLLMConfig,
    updateUserSettings,
    setError,
  };
};