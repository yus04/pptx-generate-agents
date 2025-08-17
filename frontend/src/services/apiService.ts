import axios from 'axios';
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
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized access
      localStorage.removeItem('authToken');
      window.location.href = '/';
    }
    return Promise.reject(error);
  }
);

export const apiService = {
  // Slide generation
  async generateSlides(request: SlideGenerationRequest): Promise<{ job_id: string; status: string }> {
    const response = await apiClient.post('/generate-slides', request);
    return response.data;
  },

  async approveAgenda(jobId: string, approved: boolean, agenda?: any): Promise<{ status: string }> {
    const response = await apiClient.post('/approve-agenda', {
      job_id: jobId,
      approved,
      agenda,
    });
    return response.data;
  },

  async getJobStatus(jobId: string): Promise<SlideGenerationJob> {
    const response = await apiClient.get(`/jobs/${jobId}`);
    return response.data;
  },

  async getUserJobs(): Promise<SlideGenerationJob[]> {
    const response = await apiClient.get('/jobs');
    return response.data;
  },

  async getGenerationHistory(): Promise<GenerationHistory[]> {
    const response = await apiClient.get('/history');
    return response.data;
  },

  // Template management
  async uploadTemplate(file: File, name: string, description: string): Promise<SlideTemplate> {
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
    const response = await apiClient.get('/templates');
    return response.data;
  },

  async deleteTemplate(templateId: string): Promise<void> {
    await apiClient.delete(`/templates/${templateId}`);
  },

  // Prompt templates
  async getPromptTemplates(): Promise<PromptTemplate[]> {
    const response = await apiClient.get('/prompt-templates');
    return response.data;
  },

  async createPromptTemplate(template: Omit<PromptTemplate, 'id' | 'user_id' | 'created_at'>): Promise<PromptTemplate> {
    const response = await apiClient.post('/prompt-templates', template);
    return response.data;
  },

  async updatePromptTemplate(templateId: string, template: Partial<PromptTemplate>): Promise<PromptTemplate> {
    const response = await apiClient.put(`/prompt-templates/${templateId}`, template);
    return response.data;
  },

  async deletePromptTemplate(templateId: string): Promise<void> {
    await apiClient.delete(`/prompt-templates/${templateId}`);
  },

  // LLM configurations
  async getLLMConfigs(): Promise<LLMConfig[]> {
    const response = await apiClient.get('/llm-configs');
    return response.data;
  },

  async createLLMConfig(config: Omit<LLMConfig, 'id' | 'user_id' | 'created_at'>): Promise<LLMConfig> {
    const response = await apiClient.post('/llm-configs', config);
    return response.data;
  },

  async updateLLMConfig(configId: string, config: Partial<LLMConfig>): Promise<LLMConfig> {
    const response = await apiClient.put(`/llm-configs/${configId}`, config);
    return response.data;
  },

  async deleteLLMConfig(configId: string): Promise<void> {
    await apiClient.delete(`/llm-configs/${configId}`);
  },

  // User settings
  async getUserSettings(): Promise<UserSettings> {
    const response = await apiClient.get('/user-settings');
    return response.data;
  },

  async updateUserSettings(settings: Partial<UserSettings>): Promise<UserSettings> {
    const response = await apiClient.put('/user-settings', settings);
    return response.data;
  },
};

export default apiService;