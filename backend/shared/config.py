from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # Azure Authentication
    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: str
    
    # Azure Cosmos DB
    cosmos_db_endpoint: str
    cosmos_db_key: str
    cosmos_db_database_name: str = "pptx_generator"
    
    # Azure Blob Storage
    blob_storage_connection_string: str
    blob_container_name: str = "slides"
    
    # Azure AI Foundry
    azure_ai_foundry_endpoint: str
    azure_ai_foundry_key: str
    
    # OpenTelemetry
    otel_service_name: str = "pptx-generator"
    otel_exporter_endpoint: Optional[str] = None
    
    # A2A Settings
    a2a_port: int = 8000
    a2a_host: str = "0.0.0.0"
    a2a_token_secret: str
    
    # API Settings
    api_cors_origins: List[str] = ["http://localhost:3000"]
    api_debug: bool = False
    
    # Default configurations
    default_llm_model: str = "gpt-4"
    default_temperature: float = 0.7
    default_max_tokens: int = 2000
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()