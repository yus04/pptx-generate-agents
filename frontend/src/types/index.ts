export interface SlideTemplate {
  id: string;
  name: string;
  description: string;
  blob_url: string;
  user_id: string;
  created_at: string;
}

export interface PromptTemplate {
  id: string;
  name: string;
  prompt: string;
  description: string;
  user_id: string;
  is_default: boolean;
  created_at: string;
}

export interface LLMConfig {
  id: string;
  name: string;
  provider: 'azure_openai' | 'openai' | 'anthropic';
  model_name: string;
  temperature: number;
  max_tokens: number;
  user_id: string;
  is_default: boolean;
  created_at: string;
}

export interface SlideContent {
  page_number: number;
  title: string;
  content: string;
  notes?: string;
  images: string[];
  tables: any[];
}

export interface SlideAgenda {
  slides: SlideContent[];
  total_pages: number;
  estimated_duration: number;
}

export interface SlideGenerationRequest {
  prompt: string;
  reference_urls: string[];
  slide_template_id?: string;
  llm_config_id?: string;
  max_slides: number;
  auto_approval: boolean;
  include_images: boolean;
  include_tables: boolean;
}

export interface SlideGenerationJob {
  id: string;
  user_id: string;
  request: SlideGenerationRequest;
  status: 'pending' | 'agenda_generation' | 'agenda_approval' | 'information_collection' | 'slide_creation' | 'review' | 'completed' | 'failed';
  agenda?: SlideAgenda;
  progress: number;
  current_step: string;
  result_blob_url?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface GenerationHistory {
  id: string;
  user_id: string;
  job_id: string;
  title: string;
  slide_count: number;
  blob_url: string;
  created_at: string;
}

export interface UserSettings {
  user_id: string;
  default_llm_config_id?: string;
  default_template_id?: string;
  auto_approval: boolean;
  notification_enabled: boolean;
  created_at: string;
  updated_at: string;
}