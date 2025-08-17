from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional, Dict, Any
import uuid
import asyncio
from datetime import datetime

from a2a.types import AgentCard, AgentSkill
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.apps import A2AStarletteApplication
from a2a.client import A2AClient

from ..shared.models import (
    SlideGenerationRequest, SlideGenerationJob, SlideGenerationStatus,
    SlideTemplate, PromptTemplate, LLMConfig, UserSettings, GenerationHistory,
    AgentRequest, AgentResponse
)
from ..shared.storage import cosmos_client, blob_client
from ..shared.auth import auth_manager
from ..shared.config import settings


class OrchestrationExecutor(AgentExecutor):
    async def execute(self, request: AgentRequest) -> AgentResponse:
        """オーケストレーションエージェントのメイン実行ロジック"""
        try:
            if request.agent_type == "slide_generation":
                return await self._handle_slide_generation(request)
            elif request.agent_type == "agenda_approval":
                return await self._handle_agenda_approval(request)
            else:
                return AgentResponse(
                    request_id=request.request_id,
                    success=False,
                    error=f"Unknown agent type: {request.agent_type}"
                )
        except Exception as e:
            return AgentResponse(
                request_id=request.request_id,
                success=False,
                error=str(e)
            )
    
    async def cancel(self, request_id: str) -> bool:
        """実行中のジョブをキャンセル"""
        # TODO: ジョブキャンセル実装
        return True
    
    async def _handle_slide_generation(self, request: AgentRequest) -> AgentResponse:
        """スライド生成フローの開始"""
        gen_request = SlideGenerationRequest(**request.payload)
        job_id = str(uuid.uuid4())
        
        # ジョブをデータベースに保存
        job = SlideGenerationJob(
            id=job_id,
            user_id=request.user_id,
            request=gen_request,
            status=SlideGenerationStatus.AGENDA_GENERATION,
            current_step="アジェンダ生成中..."
        )
        
        cosmos_client.create_item("slide_jobs", job.dict())
        
        # バックグラウンドでスライド生成を開始
        asyncio.create_task(self._process_slide_generation(job))
        
        return AgentResponse(
            request_id=request.request_id,
            success=True,
            result={"job_id": job_id, "status": job.status},
            progress=10
        )
    
    async def _process_slide_generation(self, job: SlideGenerationJob):
        """スライド生成の全フローを実行"""
        try:
            # 1. アジェンダ生成
            agenda_client = A2AClient("http://agenda-agent:8001")
            agenda_response = await agenda_client.call_agent(AgentRequest(
                request_id=str(uuid.uuid4()),
                agent_type="generate_agenda",
                payload=job.request.dict(),
                user_id=job.user_id
            ))
            
            if not agenda_response.success:
                raise Exception(f"Agenda generation failed: {agenda_response.error}")
            
            job.agenda = agenda_response.result
            job.status = SlideGenerationStatus.AGENDA_APPROVAL
            job.progress = 25
            job.current_step = "アジェンダ承認待ち..."
            await self._update_job(job)
            
            # 自動承認設定確認
            if job.request.auto_approval:
                await self._continue_after_approval(job)
            
        except Exception as e:
            job.status = SlideGenerationStatus.FAILED
            job.error_message = str(e)
            job.current_step = "エラーが発生しました"
            await self._update_job(job)
    
    async def _continue_after_approval(self, job: SlideGenerationJob):
        """アジェンダ承認後の処理続行"""
        try:
            # 2. 情報収集
            job.status = SlideGenerationStatus.INFORMATION_COLLECTION
            job.progress = 50
            job.current_step = "情報収集中..."
            await self._update_job(job)
            
            info_client = A2AClient("http://information-agent:8002")
            info_response = await info_client.call_agent(AgentRequest(
                request_id=str(uuid.uuid4()),
                agent_type="collect_information",
                payload={
                    "agenda": job.agenda.dict(),
                    "reference_urls": job.request.reference_urls
                },
                user_id=job.user_id
            ))
            
            if not info_response.success:
                raise Exception(f"Information collection failed: {info_response.error}")
            
            # 3. スライド作成
            job.status = SlideGenerationStatus.SLIDE_CREATION
            job.progress = 75
            job.current_step = "スライド作成中..."
            await self._update_job(job)
            
            slide_client = A2AClient("http://slide-agent:8003")
            slide_response = await slide_client.call_agent(AgentRequest(
                request_id=str(uuid.uuid4()),
                agent_type="create_slides",
                payload={
                    "agenda": job.agenda.dict(),
                    "information": info_response.result,
                    "template_id": job.request.slide_template_id,
                    "include_images": job.request.include_images,
                    "include_tables": job.request.include_tables
                },
                user_id=job.user_id
            ))
            
            if not slide_response.success:
                raise Exception(f"Slide creation failed: {slide_response.error}")
            
            # 4. レビュー
            job.status = SlideGenerationStatus.REVIEW
            job.progress = 90
            job.current_step = "品質チェック中..."
            await self._update_job(job)
            
            review_client = A2AClient("http://review-agent:8004")
            review_response = await review_client.call_agent(AgentRequest(
                request_id=str(uuid.uuid4()),
                agent_type="review_slides",
                payload={
                    "slide_url": slide_response.result["slide_url"],
                    "agenda": job.agenda.dict()
                },
                user_id=job.user_id
            ))
            
            # 完了
            job.status = SlideGenerationStatus.COMPLETED
            job.progress = 100
            job.current_step = "完了"
            job.result_blob_url = slide_response.result["slide_url"]
            await self._update_job(job)
            
            # 履歴に追加
            history = GenerationHistory(
                id=str(uuid.uuid4()),
                user_id=job.user_id,
                job_id=job.id,
                title=job.agenda.slides[0].title if job.agenda and job.agenda.slides else "無題",
                slide_count=len(job.agenda.slides) if job.agenda else 0,
                blob_url=job.result_blob_url
            )
            cosmos_client.create_item("generation_history", history.dict())
            
        except Exception as e:
            job.status = SlideGenerationStatus.FAILED
            job.error_message = str(e)
            job.current_step = "エラーが発生しました"
            await self._update_job(job)
    
    async def _handle_agenda_approval(self, request: AgentRequest) -> AgentResponse:
        """アジェンダ承認処理"""
        job_id = request.payload.get("job_id")
        approved = request.payload.get("approved", False)
        updated_agenda = request.payload.get("agenda")
        
        job_data = cosmos_client.read_item("slide_jobs", job_id, request.user_id)
        if not job_data:
            return AgentResponse(
                request_id=request.request_id,
                success=False,
                error="Job not found"
            )
        
        job = SlideGenerationJob(**job_data)
        
        if approved:
            if updated_agenda:
                job.agenda = updated_agenda
            asyncio.create_task(self._continue_after_approval(job))
        else:
            job.status = SlideGenerationStatus.FAILED
            job.error_message = "User rejected agenda"
            await self._update_job(job)
        
        return AgentResponse(
            request_id=request.request_id,
            success=True,
            result={"status": job.status}
        )
    
    async def _update_job(self, job: SlideGenerationJob):
        """ジョブステータスを更新"""
        job.updated_at = datetime.utcnow()
        cosmos_client.update_item("slide_jobs", job.dict())


# Agent setup
agent_card = AgentCard(
    name="PowerPoint Slide Generation Orchestrator",
    description="PowerPoint スライド生成の全体フローを管理するオーケストレーションエージェント",
    version="1.0.0"
)

agent_skills = [
    AgentSkill(
        name="slide_generation",
        description="スライド生成フローの開始"
    ),
    AgentSkill(
        name="agenda_approval", 
        description="アジェンダ承認処理"
    )
]

executor = OrchestrationExecutor()
request_handler = DefaultRequestHandler(agent_card, agent_skills, executor)

# FastAPI app
app = FastAPI(title="PowerPoint Slide Generation Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()


def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """認証されたユーザーIDを取得"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    user_id = auth_manager.extract_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return user_id


@app.post("/generate-slides")
async def generate_slides(
    request: SlideGenerationRequest,
    user_id: str = Depends(get_current_user)
):
    """スライド生成を開始"""
    agent_request = AgentRequest(
        request_id=str(uuid.uuid4()),
        agent_type="slide_generation",
        payload=request.dict(),
        user_id=user_id
    )
    
    response = await executor.execute(agent_request)
    if not response.success:
        raise HTTPException(status_code=500, detail=response.error)
    
    return response.result


@app.post("/approve-agenda")
async def approve_agenda(
    job_id: str,
    approved: bool,
    agenda: Optional[Dict[str, Any]] = None,
    user_id: str = Depends(get_current_user)
):
    """アジェンダを承認/拒否"""
    agent_request = AgentRequest(
        request_id=str(uuid.uuid4()),
        agent_type="agenda_approval",
        payload={
            "job_id": job_id,
            "approved": approved,
            "agenda": agenda
        },
        user_id=user_id
    )
    
    response = await executor.execute(agent_request)
    if not response.success:
        raise HTTPException(status_code=500, detail=response.error)
    
    return response.result


@app.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    user_id: str = Depends(get_current_user)
):
    """ジョブステータスを取得"""
    job_data = cosmos_client.read_item("slide_jobs", job_id, user_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_data


@app.get("/jobs")
async def get_user_jobs(user_id: str = Depends(get_current_user)):
    """ユーザーのジョブ一覧を取得"""
    jobs = cosmos_client.get_user_items("slide_jobs", user_id)
    return jobs


@app.get("/history")
async def get_generation_history(user_id: str = Depends(get_current_user)):
    """生成履歴を取得"""
    history = cosmos_client.get_user_items("generation_history", user_id)
    return history


# Template management endpoints
@app.post("/templates")
async def upload_template(
    file: UploadFile = File(...),
    name: str = "",
    description: str = "",
    user_id: str = Depends(get_current_user)
):
    """スライドテンプレートをアップロード"""
    if not file.filename.endswith('.pptx'):
        raise HTTPException(status_code=400, detail="Only .pptx files are allowed")
    
    blob_url = blob_client.upload_file(
        file.file, file.filename, user_id, "templates"
    )
    
    template = SlideTemplate(
        id=str(uuid.uuid4()),
        name=name or file.filename,
        description=description,
        blob_url=blob_url,
        user_id=user_id
    )
    
    cosmos_client.create_item("slide_templates", template.dict())
    return template.dict()


@app.get("/templates")
async def get_templates(user_id: str = Depends(get_current_user)):
    """ユーザーのテンプレート一覧を取得"""
    templates = cosmos_client.get_user_items("slide_templates", user_id)
    return templates


@app.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """テンプレートを削除"""
    template_data = cosmos_client.read_item("slide_templates", template_id, user_id)
    if not template_data:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Blob Storage からファイルを削除
    blob_client.delete_file(template_data["blob_url"])
    
    # データベースから削除
    cosmos_client.delete_item("slide_templates", template_id, user_id)
    
    return {"message": "Template deleted successfully"}


# Prompt template management endpoints
@app.get("/prompt-templates")
async def get_prompt_templates(user_id: str = Depends(get_current_user)):
    """プロンプトテンプレート一覧を取得"""
    templates = cosmos_client.get_user_items("prompt_templates", user_id)
    return templates


@app.post("/prompt-templates")
async def create_prompt_template(
    template: Dict[str, Any],
    user_id: str = Depends(get_current_user)
):
    """プロンプトテンプレートを作成"""
    prompt_template = PromptTemplate(
        id=str(uuid.uuid4()),
        name=template["name"],
        prompt=template["prompt"],
        description=template.get("description", ""),
        user_id=user_id,
        is_default=template.get("is_default", False)
    )
    
    cosmos_client.create_item("prompt_templates", prompt_template.dict())
    return prompt_template.dict()


@app.put("/prompt-templates/{template_id}")
async def update_prompt_template(
    template_id: str,
    template: Dict[str, Any],
    user_id: str = Depends(get_current_user)
):
    """プロンプトテンプレートを更新"""
    existing_template = cosmos_client.read_item("prompt_templates", template_id, user_id)
    if not existing_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # 更新データをマージ
    existing_template.update(template)
    existing_template["updated_at"] = datetime.utcnow().isoformat()
    
    cosmos_client.update_item("prompt_templates", existing_template)
    return existing_template


@app.delete("/prompt-templates/{template_id}")
async def delete_prompt_template(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """プロンプトテンプレートを削除"""
    template_data = cosmos_client.read_item("prompt_templates", template_id, user_id)
    if not template_data:
        raise HTTPException(status_code=404, detail="Template not found")
    
    cosmos_client.delete_item("prompt_templates", template_id, user_id)
    return {"message": "Prompt template deleted successfully"}


# LLM configuration endpoints
@app.get("/llm-configs")
async def get_llm_configs(user_id: str = Depends(get_current_user)):
    """LLM設定一覧を取得"""
    configs = cosmos_client.get_user_items("llm_configs", user_id)
    return configs


@app.post("/llm-configs")
async def create_llm_config(
    config: Dict[str, Any],
    user_id: str = Depends(get_current_user)
):
    """LLM設定を作成"""
    llm_config = LLMConfig(
        id=str(uuid.uuid4()),
        name=config["name"],
        provider=config["provider"],
        model_name=config["model_name"],
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 2000),
        user_id=user_id,
        is_default=config.get("is_default", False)
    )
    
    cosmos_client.create_item("llm_configs", llm_config.dict())
    return llm_config.dict()


@app.put("/llm-configs/{config_id}")
async def update_llm_config(
    config_id: str,
    config: Dict[str, Any],
    user_id: str = Depends(get_current_user)
):
    """LLM設定を更新"""
    existing_config = cosmos_client.read_item("llm_configs", config_id, user_id)
    if not existing_config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    existing_config.update(config)
    existing_config["updated_at"] = datetime.utcnow().isoformat()
    
    cosmos_client.update_item("llm_configs", existing_config)
    return existing_config


@app.delete("/llm-configs/{config_id}")
async def delete_llm_config(
    config_id: str,
    user_id: str = Depends(get_current_user)
):
    """LLM設定を削除"""
    config_data = cosmos_client.read_item("llm_configs", config_id, user_id)
    if not config_data:
        raise HTTPException(status_code=404, detail="Config not found")
    
    cosmos_client.delete_item("llm_configs", config_id, user_id)
    return {"message": "LLM config deleted successfully"}


# User settings endpoints
@app.get("/user-settings")
async def get_user_settings(user_id: str = Depends(get_current_user)):
    """ユーザー設定を取得"""
    settings_data = cosmos_client.read_item("users", user_id, user_id)
    if not settings_data:
        # デフォルト設定を作成
        default_settings = UserSettings(
            user_id=user_id,
            auto_approval=False,
            notification_enabled=True
        )
        cosmos_client.create_item("users", default_settings.dict())
        return default_settings.dict()
    
    return settings_data


@app.put("/user-settings")
async def update_user_settings(
    settings: Dict[str, Any],
    user_id: str = Depends(get_current_user)
):
    """ユーザー設定を更新"""
    existing_settings = cosmos_client.read_item("users", user_id, user_id)
    if not existing_settings:
        # 新規作成
        user_settings = UserSettings(
            user_id=user_id,
            **settings
        )
        cosmos_client.create_item("users", user_settings.dict())
        return user_settings.dict()
    else:
        # 既存設定を更新
        existing_settings.update(settings)
        existing_settings["updated_at"] = datetime.utcnow().isoformat()
        cosmos_client.update_item("users", existing_settings)
        return existing_settings


# Create A2A application
a2a_app = A2AStarletteApplication(app, request_handler)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        a2a_app,
        host=settings.a2a_host,
        port=settings.a2a_port
    )