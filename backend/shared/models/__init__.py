from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SlideGenerationStatus(str, Enum):
    PENDING = "pending"
    AGENDA_GENERATION = "agenda_generation"
    AGENDA_APPROVAL = "agenda_approval"
    INFORMATION_COLLECTION = "information_collection"
    SLIDE_CREATION = "slide_creation"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"


class LLMProvider(str, Enum):
    AZURE_OPENAI = "azure_openai"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class SlideTemplate(BaseModel):
    id: str = Field(..., description="テンプレートID")
    name: str = Field(..., description="テンプレート名")
    description: str = Field(..., description="テンプレートの説明")
    blob_url: str = Field(..., description="Blob Storage URL")
    user_id: str = Field(..., description="アップロードユーザーID")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PromptTemplate(BaseModel):
    id: str = Field(..., description="プロンプトテンプレートID")
    name: str = Field(..., description="テンプレート名")
    prompt: str = Field(..., description="プロンプト内容")
    description: str = Field(..., description="テンプレートの説明")
    user_id: str = Field(..., description="作成ユーザーID")
    is_default: bool = Field(default=False, description="デフォルトテンプレート")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LLMConfig(BaseModel):
    id: str = Field(..., description="LLM設定ID")
    name: str = Field(..., description="設定名")
    provider: LLMProvider = Field(..., description="LLMプロバイダー")
    model_name: str = Field(..., description="モデル名")
    temperature: float = Field(default=0.7, description="Temperature")
    max_tokens: int = Field(default=2000, description="最大トークン数")
    user_id: str = Field(..., description="設定ユーザーID")
    is_default: bool = Field(default=False, description="デフォルト設定")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SlideContent(BaseModel):
    page_number: int = Field(..., description="ページ番号")
    title: str = Field(..., description="スライドタイトル")
    content: str = Field(..., description="スライド内容")
    notes: Optional[str] = Field(None, description="ノート（ハルシネーション警告等）")
    images: List[str] = Field(default=[], description="画像URL一覧")
    tables: List[Dict[str, Any]] = Field(default=[], description="テーブルデータ")


class SlideAgenda(BaseModel):
    slides: List[SlideContent] = Field(..., description="スライド一覧")
    total_pages: int = Field(..., description="総ページ数")
    estimated_duration: int = Field(..., description="推定所要時間（分）")


class SlideGenerationRequest(BaseModel):
    prompt: str = Field(..., description="生成プロンプト")
    reference_urls: List[str] = Field(default=[], description="参照URL一覧")
    slide_template_id: Optional[str] = Field(None, description="スライドテンプレートID")
    llm_config_id: Optional[str] = Field(None, description="LLM設定ID")
    max_slides: int = Field(default=10, description="最大スライド数")
    auto_approval: bool = Field(default=False, description="自動承認")
    include_images: bool = Field(default=True, description="画像を含める")
    include_tables: bool = Field(default=True, description="テーブルを含める")


class SlideGenerationJob(BaseModel):
    id: str = Field(..., description="ジョブID")
    user_id: str = Field(..., description="ユーザーID")
    request: SlideGenerationRequest = Field(..., description="生成リクエスト")
    status: SlideGenerationStatus = Field(..., description="ステータス")
    agenda: Optional[SlideAgenda] = Field(None, description="生成されたアジェンダ")
    progress: int = Field(default=0, description="進捗率（0-100）")
    current_step: str = Field(default="", description="現在の処理ステップ")
    result_blob_url: Optional[str] = Field(None, description="結果ファイルのURL")
    error_message: Optional[str] = Field(None, description="エラーメッセージ")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserSettings(BaseModel):
    user_id: str = Field(..., description="ユーザーID")
    default_llm_config_id: Optional[str] = Field(None, description="デフォルトLLM設定ID")
    default_template_id: Optional[str] = Field(None, description="デフォルトテンプレートID")
    auto_approval: bool = Field(default=False, description="自動承認設定")
    notification_enabled: bool = Field(default=True, description="通知有効")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GenerationHistory(BaseModel):
    id: str = Field(..., description="履歴ID")
    user_id: str = Field(..., description="ユーザーID")
    job_id: str = Field(..., description="ジョブID")
    title: str = Field(..., description="スライドタイトル")
    slide_count: int = Field(..., description="スライド数")
    blob_url: str = Field(..., description="ファイルURL")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Agent communication models
class AgentRequest(BaseModel):
    request_id: str = Field(..., description="リクエストID")
    agent_type: str = Field(..., description="エージェントタイプ")
    payload: Dict[str, Any] = Field(..., description="ペイロード")
    user_id: str = Field(..., description="ユーザーID")


class AgentResponse(BaseModel):
    request_id: str = Field(..., description="リクエストID")
    success: bool = Field(..., description="成功フラグ")
    result: Optional[Dict[str, Any]] = Field(None, description="結果")
    error: Optional[str] = Field(None, description="エラーメッセージ")
    progress: int = Field(default=100, description="進捗率")