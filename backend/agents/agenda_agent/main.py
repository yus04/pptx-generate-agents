from fastapi import FastAPI
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.prompt_template import PromptTemplateConfig
from semantic_kernel.functions import KernelArguments
from typing import List, Dict, Any
import json

from a2a_python_sdk import (
    AgentCard, AgentSkill, AgentExecutor, DefaultRequestHandler,
    A2AStarletteApplication
)

from ...shared.models import AgentRequest, AgentResponse, SlideContent, SlideAgenda
from ...shared.config import settings


class AgendaGenerationExecutor(AgentExecutor):
    def __init__(self):
        self.kernel = Kernel()
        
        # Azure OpenAI service setup
        self.chat_service = AzureChatCompletion(
            deployment_name=settings.default_llm_model,
            endpoint=settings.azure_ai_foundry_endpoint,
            api_key=settings.azure_ai_foundry_key
        )
        self.kernel.add_service(self.chat_service)
        
        self._setup_prompts()
    
    def _setup_prompts(self):
        """プロンプトテンプレートを設定"""
        agenda_prompt = """
あなたはPowerPointスライドのアジェンダ生成の専門家です。
与えられたプロンプトに基づいて、効果的なプレゼンテーションスライドの構成を作成してください。

## 入力情報
プロンプト: {{$prompt}}
最大スライド数: {{$max_slides}}
参照URL: {{$reference_urls}}

## 出力要件
1. スライド構成は論理的で流れが自然であること
2. 各スライドには明確なタイトルと概要を含めること
3. プレゼンテーションの開始（タイトルスライド）と終了（まとめ）を含めること
4. 技術的な内容の場合は、図表や画像が効果的な箇所を示唆すること

## 出力形式
以下のJSON形式で出力してください：
```json
{
  "slides": [
    {
      "page_number": 1,
      "title": "スライドタイトル",
      "content": "スライドの概要説明（200文字程度）",
      "notes": null,
      "images": [],
      "tables": []
    }
  ],
  "total_pages": 総ページ数,
  "estimated_duration": 推定発表時間（分）
}
```

スライド構成を生成してください：
"""
        
        prompt_config = PromptTemplateConfig(
            template=agenda_prompt,
            name="agenda_generation",
            description="スライドアジェンダ生成",
            input_variables=["prompt", "max_slides", "reference_urls"]
        )
        
        self.agenda_function = self.kernel.add_function(
            plugin_name="AgendaPlugin",
            function_name="generate_agenda",
            prompt_template_config=prompt_config
        )
    
    async def execute(self, request: AgentRequest) -> AgentResponse:
        """アジェンダ生成を実行"""
        try:
            payload = request.payload
            prompt = payload.get("prompt", "")
            max_slides = payload.get("max_slides", 10)
            reference_urls = payload.get("reference_urls", [])
            
            if not prompt:
                return AgentResponse(
                    request_id=request.request_id,
                    success=False,
                    error="Prompt is required"
                )
            
            # Semantic Kernel でアジェンダ生成
            arguments = KernelArguments(
                prompt=prompt,
                max_slides=str(max_slides),
                reference_urls="\n".join(reference_urls) if reference_urls else "なし"
            )
            
            result = await self.kernel.invoke(self.agenda_function, arguments)
            agenda_text = str(result)
            
            # JSON パース
            try:
                # JSONブロックを抽出
                if "```json" in agenda_text:
                    start = agenda_text.find("```json") + 7
                    end = agenda_text.find("```", start)
                    agenda_text = agenda_text[start:end].strip()
                
                agenda_data = json.loads(agenda_text)
                agenda = SlideAgenda(**agenda_data)
                
                return AgentResponse(
                    request_id=request.request_id,
                    success=True,
                    result=agenda.dict()
                )
                
            except (json.JSONDecodeError, ValueError) as e:
                # フォールバック: シンプルなアジェンダ生成
                agenda = self._create_fallback_agenda(prompt, max_slides)
                return AgentResponse(
                    request_id=request.request_id,
                    success=True,
                    result=agenda.dict()
                )
        
        except Exception as e:
            return AgentResponse(
                request_id=request.request_id,
                success=False,
                error=str(e)
            )
    
    async def cancel(self, request_id: str) -> bool:
        """処理をキャンセル"""
        return True
    
    def _create_fallback_agenda(self, prompt: str, max_slides: int) -> SlideAgenda:
        """フォールバック用のシンプルなアジェンダ生成"""
        slides = [
            SlideContent(
                page_number=1,
                title="タイトルスライド",
                content=f"プレゼンテーションのタイトル: {prompt[:50]}..."
            )
        ]
        
        # 中間スライドを生成
        content_slides = min(max_slides - 2, 8)  # タイトルとまとめを除く
        for i in range(content_slides):
            slides.append(SlideContent(
                page_number=i + 2,
                title=f"セクション {i + 1}",
                content="このセクションの詳細内容を記載します。"
            ))
        
        # まとめスライド
        slides.append(SlideContent(
            page_number=len(slides) + 1,
            title="まとめ",
            content="プレゼンテーションの要点をまとめます。"
        ))
        
        return SlideAgenda(
            slides=slides,
            total_pages=len(slides),
            estimated_duration=len(slides) * 2  # 1スライド2分として推定
        )


# Agent setup
agent_card = AgentCard(
    name="Agenda Generation Agent",
    description="PowerPoint スライドのアジェンダを生成するエージェント",
    version="1.0.0"
)

agent_skills = [
    AgentSkill(
        name="generate_agenda",
        description="プロンプトからスライドアジェンダを生成"
    )
]

executor = AgendaGenerationExecutor()
request_handler = DefaultRequestHandler(agent_card, agent_skills, executor)

# FastAPI app
app = FastAPI(title="Agenda Generation Agent")

# Create A2A application
a2a_app = A2AStarletteApplication(app, request_handler)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(a2a_app, host="0.0.0.0", port=8001)