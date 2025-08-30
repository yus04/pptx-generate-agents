from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.prompt_template import PromptTemplateConfig, InputVariable
from semantic_kernel.functions import KernelArguments
import json
import uvicorn

from a2a.types import AgentCard, AgentSkill, DataPart, Message, TextPart, Part, Role
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.apps import A2AStarletteApplication
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.agent_execution import RequestContext
from a2a.server.events.event_queue import EventQueue

from shared.models import SlideContent, SlideAgenda
from shared.config import settings
import uuid

class AgendaGenerationExecutor(AgentExecutor):
    def __init__(self):
        self.kernel = Kernel()
        
        # Azure OpenAI service setup
        self.chat_service = AzureChatCompletion(
            deployment_name=settings.azure_ai_foundry_model_deployment,
            endpoint=settings.azure_ai_foundry_chat_endpoint,
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
            input_variables=[
                InputVariable(name="prompt", description="プレゼンテーションのプロンプト"),
                InputVariable(name="max_slides", description="最大スライド数"),
                InputVariable(name="reference_urls", description="参照URL")
            ]
        )
        
        self.agenda_function = self.kernel.add_function(
            plugin_name="AgendaPlugin",
            function_name="generate_agenda",
            prompt_template_config=prompt_config
        )
    
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """アジェンダ生成を実行"""
        try:
            # RequestContext から必要な情報を取得
            parts = context.message.parts
            if not parts or len(parts) == 0:
                print("✗ Error: Message parts are required")
                return
            payload_part = parts[0]
            if not isinstance(payload_part.root, DataPart):
                print("✗ Error: First part must be DataPart")
                return
            
            # payloadが既に辞書の場合と文字列の場合を処理
            raw_data = payload_part.root.data
            if isinstance(raw_data, dict):
                data_part = raw_data
            else:
                data_part = json.loads(raw_data)
            print(f"   ✓ Received data part: {data_part}")                       

            payload = data_part.get("payload", {})
            prompt = payload.get("prompt", "")
            max_slides = payload.get("max_slides", 10)
            reference_urls = payload.get("reference_urls", [])
            print(f"   ✓ Received prompt: {prompt[:50]}..., max_slides: {max_slides}, reference_urls: {reference_urls}")
            
            if not prompt:
                print("✗ Error: Prompt is required")
                return
            
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
                # agenda_text が既に辞書の場合の処理を追加
                if isinstance(agenda_text, dict):
                    agenda_data = agenda_text
                else:
                    agenda_text = str(result)
                
                print(f"   ✓ Agenda text type: {type(agenda_text)}")
                print(f"   ✓ Agenda text: {agenda_text[:200]}...")
                
                # JSONブロックを抽出
                if "```json" in agenda_text:
                    json_start = agenda_text.find("```json") + 7
                    json_end = agenda_text.find("```", json_start)
                    agenda_json = agenda_text[json_start:json_end].strip()
                else:
                    agenda_json = agenda_text.strip()
                
                print(f"   ✓ Extracted JSON: {agenda_json[:200]}...")
                
                # JSON文字列をパース
                agenda_data = json.loads(agenda_json)
                print(f"   ✓ Parsed JSON successfully: {type(agenda_data)}")

                # SlideAgenda に変換
                slides = []
                for slide_data in agenda_data.get("slides", []):
                    slide = SlideContent(
                        page_number=slide_data.get("page_number", 0),
                        title=slide_data.get("title", ""),
                        content=slide_data.get("content", "")
                    )
                    slides.append(slide)
                
                agenda = SlideAgenda(
                    total_pages=agenda_data.get("total_pages", len(slides)),
                    slides=slides,
                    estimated_duration=agenda_data.get("estimated_duration", len(slides) * 2)  # 1スライド2分の推定
                )
                
                # 結果をEventQueueに送信
                result_json = json.dumps(agenda.model_dump(), ensure_ascii=False)
                message = Message(
                    message_id=str(uuid.uuid4()),
                    role=Role.agent,
                    context_id=context.message.context_id,
                    parts=[Part(root=TextPart(text=result_json))]
                )
                await event_queue.enqueue_event(message)
                print(f"   ✓ Result sent to EventQueue: {len(result_json)} characters")
                
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                print(f"   ✗ JSON parsing error: {str(e)}")
                # フォールバック: シンプルなアジェンダ生成
                agenda = self._create_fallback_agenda(prompt, max_slides)
                result_json = json.dumps(agenda.model_dump(), ensure_ascii=False)
                message = Message(
                    message_id=str(uuid.uuid4()),
                    role=Role.agent,
                    context_id=context.message.context_id,
                    parts=[Part(root=TextPart(text=result_json))]
                )
                await event_queue.enqueue_event(message)
                print(f"   ✓ Fallback result sent to EventQueue")
        
        except Exception as e:
            print(f"✗ Error during agenda generation: {str(e)}")
            # エラー時もEventQueueに結果を送信
            try:
                fallback_agenda = self._create_fallback_agenda(prompt if 'prompt' in locals() else "エラーが発生しました", 5)
                result_json = json.dumps(fallback_agenda.model_dump(), ensure_ascii=False)
                message = Message(
                    message_id=str(uuid.uuid4()),
                    role=Role.agent,
                    context_id=context.message.context_id if hasattr(context, 'message') and hasattr(context.message, 'conversation_id') else str(uuid.uuid4()),
                    parts=[Part(root=TextPart(text=result_json))]
                )
                await event_queue.enqueue_event(message)
                print(f"   ✓ Error fallback result sent to EventQueue")
            except Exception as fallback_error:
                print(f"   ✗ Failed to send fallback result: {str(fallback_error)}")
                # 最小限のエラーレスポンスを送信
                try:
                    error_response = {
                        "error": "アジェンダ生成に失敗しました",
                        "details": str(e)
                    }
                    message = Message(
                        message_id=str(uuid.uuid4()),
                        role=Role.agent,
                        context_id=context.message.context_id if hasattr(context, 'message') and hasattr(context.message, 'conversation_id') else str(uuid.uuid4()),
                        parts=[Part(root=TextPart(text=json.dumps(error_response, ensure_ascii=False)))]
                    )
                    await event_queue.enqueue_event(message)
                except Exception:
                    print("   ✗ Failed to send any response")
    
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
            total_pages=len(slides),
            slides=slides,
            estimated_duration=len(slides) * 2  # 1スライド2分の推定
        )

if __name__ == "__main__":
    agent_skills = [
        AgentSkill(
            name="generate_agenda",
            description="プロンプトからスライドアジェンダを生成",
            id="generate_agenda",
            tags=[],
            input_modes=[],
            output_modes=[],
            examples=[]
        )
    ]

    # Agent setup
    agent_card = AgentCard(
        name="Agenda Generation Agent",
        description="PowerPoint スライドのアジェンダを生成するエージェント",
        version="1.0.0",
        url=settings.agenda_agent_url,
        skills=agent_skills,
        capabilities={},
        default_input_modes=[],
        default_output_modes=[]
    )

    executor = AgendaGenerationExecutor()
    task_store = InMemoryTaskStore()
    request_handler = DefaultRequestHandler(executor, task_store)

    # Create A2A application
    a2a_app = A2AStarletteApplication(agent_card, request_handler)

    uvicorn.run(a2a_app.build(), host="0.0.0.0", port=8001)
