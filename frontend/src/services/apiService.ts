import axios from 'axios';
import { msalInstance, loginRequest } from '../config/authConfig';
import { 
  SlideGenerationRequest, 
  SlideGenerationJob, 
  SlideTemplate, 
  PromptTemplate, 
  LLMConfig, 
  GenerationHistory,
  UserSettings
} from '../types';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

// Axios instance with default configuration
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

// Request interceptor to add auth token
const getAccessToken = async (): Promise<string> => {
  const accounts = msalInstance.getAllAccounts(); // Fixed: removed destructuring
  
  if (accounts.length === 0) {
    throw null;
  }

  try {
    // Try to get token silently first
    const response = await msalInstance.acquireTokenSilent({
      scopes: ['openid', 'profile', 'email'],
      account: accounts[0],
    });
    
    return response.accessToken;
  } catch (error) {
    console.error('Silent token acquisition failed:', error);
    
    // Fallback to interactive token acquisition
    try {
      const response = await msalInstance.acquireTokenPopup({
        scopes: ['openid', 'profile', 'email'],
        account: accounts[0],
      });
      
      return response.accessToken;
    } catch (interactiveError) {
      console.error('Interactive token acquisition failed:', interactiveError);
      throw new Error('Failed to acquire access token');
    }
  }
};

// Update the request interceptor to use the new function
apiClient.interceptors.request.use(async (config) => {
  try {
    const token = await getAccessToken();
    config.headers.Authorization = `Bearer ${token}`;
  } catch (error) {
    console.error('Failed to acquire token:', error);
    throw error;
  }
  return config;
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Clear any cached tokens and force re-authentication
      const accounts = msalInstance.getAllAccounts();
      if (accounts.length > 0) {
        try {
          const activeAccount = msalInstance.getActiveAccount() || accounts[0];
          const response = await msalInstance.acquireTokenPopup({
            scopes: loginRequest.scopes,
            account: activeAccount
          });
          // Retry the original request
          const originalRequest = error.config;
          originalRequest.headers.Authorization = `Bearer ${response.accessToken}`;
          return apiClient.request(originalRequest);
        } catch (refreshError) {
          console.error('Token refresh failed:', refreshError);
          // Force logout and redirect to login
          msalInstance.logoutRedirect();
        }
      } else {
        // No accounts available - redirect to login
        msalInstance.loginRedirect(loginRequest);
      }
    }
    return Promise.reject(error);
  }
);

const isAuthenticated = (): boolean => {
  return msalInstance.getAllAccounts().length > 0;
};

export const apiService = {
  // Slide generation
  async generateSlides(request: SlideGenerationRequest): Promise<{ job_id: string; status: string }> {
    if (!isAuthenticated()) {
      throw new Error('Authentication required');
    }
    const response = await apiClient.post('/generate-slides', request);
    return response.data;
  },

  async approveAgenda(jobId: string, approved: boolean, agenda?: any): Promise<{ status: string }> {
    if (!isAuthenticated()) {
      throw new Error('Authentication required');
    }
    const response = await apiClient.post('/approve-agenda', {
      job_id: jobId,
      approved,
      agenda,
    });
    return response.data;
  },

  async getJobStatus(jobId: string): Promise<SlideGenerationJob> {
    if (!isAuthenticated()) {
      throw new Error('Authentication required');
    }
    const response = await apiClient.get(`/jobs/${jobId}`);
    return response.data;
  },

  async getUserJobs(): Promise<SlideGenerationJob[]> {
    if (!isAuthenticated()) {
      throw new Error('Authentication required');
    }
    const response = await apiClient.get('/jobs');
    return response.data;
  },

  async getGenerationHistory(): Promise<GenerationHistory[]> {
    if (!isAuthenticated()) {
      throw new Error('Authentication required');
    }
    const response = await apiClient.get('/history');
    return response.data;
  },

  // Template management
  async uploadTemplate(file: File, name: string, description: string): Promise<SlideTemplate> {
    if (!isAuthenticated()) {
      throw new Error('Authentication required');
    }
    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', name);
    formData.append('description', description);

    const response = await apiClient.post('/templates', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async getTemplates(): Promise<SlideTemplate[]> {
    if (!isAuthenticated()) {
      return []; // 認証されていない場合は空配列を返す
    }
    const response = await apiClient.get('/templates');
    return response.data;
  },

  async deleteTemplate(templateId: string): Promise<void> {
    if (!isAuthenticated()) {
      throw new Error('Authentication required');
    }
    await apiClient.delete(`/templates/${templateId}`);
  },

  // Prompt templates
  async getPromptTemplates(): Promise<PromptTemplate[]> {
    if (!isAuthenticated()) {
      return []; // 認証されていない場合は空配列を返す
    }
    const response = await apiClient.get('/prompt-templates');
    return response.data;
  },

  async createPromptTemplate(template: Omit<PromptTemplate, 'id' | 'user_id' | 'created_at'>): Promise<PromptTemplate> {
    if (!isAuthenticated()) {
      throw new Error('Authentication required');
    }
    const response = await apiClient.post('/prompt-templates', template);
    return response.data;
  },

  async updatePromptTemplate(templateId: string, template: Partial<PromptTemplate>): Promise<PromptTemplate> {
    if (!isAuthenticated()) {
      throw new Error('Authentication required');
    }
    const response = await apiClient.put(`/prompt-templates/${templateId}`, template);
    return response.data;
  },

  async deletePromptTemplate(templateId: string): Promise<void> {
    if (!isAuthenticated()) {
      throw new Error('Authentication required');
    }
    await apiClient.delete(`/prompt-templates/${templateId}`);
  },

  // LLM configurations
  async getLLMConfigs(): Promise<LLMConfig[]> {
    if (!isAuthenticated()) {
      return []; // 認証されていない場合は空配列を返す
    }
    const response = await apiClient.get('/llm-configs');
    return response.data;
  },

  async createLLMConfig(config: Omit<LLMConfig, 'id' | 'user_id' | 'created_at'>): Promise<LLMConfig> {
    if (!isAuthenticated()) {
      throw new Error('Authentication required');
    }
    const response = await apiClient.post('/llm-configs', config);
    return response.data;
  },

  async updateLLMConfig(configId: string, config: Partial<LLMConfig>): Promise<LLMConfig> {
    if (!isAuthenticated()) {
      throw new Error('Authentication required');
    }
    const response = await apiClient.put(`/llm-configs/${configId}`, config);
    return response.data;
  },

  async deleteLLMConfig(configId: string): Promise<void> {
    if (!isAuthenticated()) {
      throw new Error('Authentication required');
    }
    await apiClient.delete(`/llm-configs/${configId}`);
  },

  // User settings
  async getUserSettings(): Promise<UserSettings> {
    if (!isAuthenticated()) {
      // 認証されていない場合はデフォルト設定を返す
      return {
        user_id: '',
        auto_approval: false,
        auto_save: true,
        theme: 'light',
        notification_enabled: true,
        default_template: undefined,
        default_llm_config: undefined,
      } as UserSettings;
    }
    const response = await apiClient.get('/user-settings');
    return response.data;
  },

  async updateUserSettings(settings: Partial<UserSettings>): Promise<UserSettings> {
    if (!isAuthenticated()) {
      throw new Error('Authentication required');
    }
    const response = await apiClient.put('/user-settings', settings);
    return response.data;
  },
};

export default apiService;