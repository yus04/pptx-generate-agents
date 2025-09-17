from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import BingGroundingTool, BingCustomSearchTool
from typing import Dict, Any, List
import json
import uvicorn
import uuid
import os

from a2a.types import AgentCard, AgentSkill, DataPart, Message, TextPart, Part, Role
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.apps import A2AStarletteApplication
from a2a.server.agent_execution import RequestContext
from a2a.server.events.event_queue import EventQueue
from shared.config import settings
from a2a.types import DataPart

class InformationCollectionExecutor(AgentExecutor):
    def __init__(self):
        self.ai_client = AIProjectClient(
            endpoint=settings.azure_ai_foundry_endpoint,
            credential=DefaultAzureCredential()
        )
        
        # Initialize Bing Search tools
        self._init_search_tools()
    
    def _init_search_tools(self):
        """Initialize Bing search tools"""
        try:
            # Bing Grounding Tool for general web search
            if hasattr(settings,'bing_connection_id'):
                self.bing_tool = BingGroundingTool(connection_id=settings.bing_connection_id)
            else:
                self.bing_tool = None
                print("Warning: Bing connection not configured")
            
            # Bing Custom Search Tool for URL-specific search
            if hasattr(settings, 'bing_custom_connection_id') and hasattr(settings, 'bing_custom_instance_name'):
                self.bing_custom_tool = BingCustomSearchTool(
                    connection_id=settings.bing_custom_connection_id,
                    instance_name=settings.bing_custom_instance_name
                )
            else:
                self.bing_custom_tool = None
                print("Warning: Bing Custom Search not configured")
                
        except Exception as e:
            print(f"Warning: Failed to initialize search tools: {e}")
            self.bing_tool = None
            self.bing_custom_tool = None
    
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """情報収集を実行"""
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
            agenda = payload.get("agenda", {})
            reference_urls = payload.get("reference_urls", [])
            
            if not agenda:
                print("✗ Error: agenda is required")
                return
            
            # 各スライドの情報を収集
            collected_info = {}
            slides = agenda.get("slides", [])
            
            for slide in slides:
                slide_num = slide.get("page_number", 0)
                slide_title = slide.get("title", "")
                slide_content = slide.get("content", "")
                
                # Microsoft Learn とBing Search で情報収集
                slide_info = await self._collect_slide_information(
                    slide_title, slide_content, reference_urls
                )
                collected_info[f"slide_{slide_num}"] = slide_info
            
            # 結果をEventQueueに送信
            result_json = json.dumps(collected_info, ensure_ascii=False)
            message = Message(
                message_id=str(uuid.uuid4()),
                role=Role.agent,
                context_id=context.message.context_id,
                parts=[Part(root=TextPart(text=result_json))]
            )
            await event_queue.enqueue_event(message)
            print(f"   ✓ Result sent to EventQueue: {len(result_json)} characters")
        
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"✗ Error processing message: {e}")
            return
    
    async def cancel(self, request_id: str) -> bool:
        """処理をキャンセル"""
        return True
    
    async def _collect_slide_information(
        self, 
        title: str, 
        content: str, 
        reference_urls: List[str]
    ) -> Dict[str, Any]:
        """個別スライドの情報を収集"""
        
        try:
            # TODO: 3 つの情報源のうち、1 つのみ利用するように対応する
            # Microsoft Learn MCP Server を使用した情報収集
            learn_info = await self._search_microsoft_learn(title, content)
            
            # 参照URLからの情報収集
            url_info = await self._collect_from_urls(reference_urls, title)
            
            # Bing Search を使用した補足情報
            bing_info = await self._search_with_bing(title, content)
                
        except Exception as e:
            print(f"Error during information collection: {e}")
            learn_info = {"text": "", "sources": [], "images": [], "tables": []}
            url_info = {"text": "", "sources": [], "images": [], "tables": []}
            bing_info = {"text": "", "sources": [], "images": [], "tables": []}
        
        return {
            "text": self._combine_information(learn_info, url_info, bing_info),
            "images": self._extract_images(learn_info, url_info, bing_info),
            "tables": self._extract_tables(learn_info, url_info, bing_info),
            "sources": reference_urls + learn_info.get("sources", [])
        }
    
    async def _search_microsoft_learn(self, title: str, content: str) -> Dict[str, Any]:
        """Microsoft Learn からの情報検索（Bing検索でlearn.microsoft.comドメインを対象）"""
        if not self.bing_tool:
            print("Bing Grounding Tool not available for Microsoft Learn search")
            return {"text": "", "sources": [], "images": [], "tables": []}
        
        try:
            # クライアントは既に with ブロック内で開かれている
            agents_client = self.ai_client.agents
            
            # Create agent for Microsoft Learn search
            agent = agents_client.create_agent(
                model=os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4"),
                name="mslearn-search-agent",
                instructions="You are a helpful agent that searches for information specifically from Microsoft Learn documentation. Focus on official Microsoft documentation and tutorials.",
                tools=self.bing_tool.definitions,
            )
            
            # Create thread for communication
            thread = agents_client.threads.create()
            
            # Create search query specifically for Microsoft Learn
            search_query = f"site:learn.microsoft.com {title} {content[:100]}"
            
            # Create message
            message = agents_client.messages.create(
                thread_id=thread.id,
                role="user",
                content=search_query,
            )
            
            # Create and process run
            run = agents_client.runs.create_and_process(
                thread_id=thread.id, 
                agent_id=agent.id
            )
            
            # Collect results
            collected_text = []
            collected_sources = []
            
            if run.status == "completed":
                # Fetch messages
                messages = agents_client.messages.list(thread_id=thread.id)
                for msg in messages:
                    if msg.role == "assistant" and msg.text_messages:
                        for text_message in msg.text_messages:
                            collected_text.append(text_message.text.value)
                    
                    # Collect URL citations, filter for Microsoft Learn URLs
                    for annotation in msg.url_citation_annotations:
                        if (annotation.url_citation and 
                            "learn.microsoft.com" in annotation.url_citation.url):
                            collected_sources.append(annotation.url_citation.url)
            elif run.status == "failed":
                print(f"Microsoft Learn search run failed: {run.last_error}")
            
            # Clean up
            agents_client.delete_agent(agent.id)
            
            return {
                "text": "\n\n".join(collected_text),
                "sources": collected_sources,
                "images": [],
                "tables": []
            }
                
        except Exception as e:
            print(f"Microsoft Learn search failed: {e}")
            return {"text": "", "sources": [], "images": [], "tables": []}
    
    async def _collect_from_urls(self, urls: List[str], topic: str) -> Dict[str, Any]:
        """指定されたURLからの情報収集（Bing Custom Search使用）"""
        if not self.bing_custom_tool:
            print("Bing Custom Search not available, falling back to simple HTTP collection")
            # return await self._collect_from_urls_simple(urls, topic)
            return {"text": "", "sources": [], "images": [], "tables": []}
        
        try:
            # クライアントは既に with ブロック内で開かれている
            agents_client = self.ai_client.agents
            
            # Create agent for custom search
            agent = agents_client.create_agent(
                model=os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4"),
                name="url-collection-agent",
                instructions=f"You are a helpful agent that collects information about '{topic}' from specific URLs. Provide detailed, relevant information.",
                tools=self.bing_custom_tool.definitions,
            )
            
            # Create thread for communication
            thread = agents_client.threads.create()
            
            # Create search query that includes the URLs and topic
            urls_text = ", ".join(urls[:5])  # Limit to first 5 URLs
            search_query = f"Find detailed information about '{topic}' from these sources: {urls_text}"
            
            # Create message
            message = agents_client.messages.create(
                thread_id=thread.id,
                role="user",
                content=search_query,
            )
            
            # Create and process run
            run = agents_client.runs.create_and_process(
                thread_id=thread.id, 
                agent_id=agent.id
            )
            
            # Collect results
            collected_text = []
            collected_sources = []
            collected_images = []
            
            if run.status == "completed":
                # Fetch messages
                messages = agents_client.messages.list(thread_id=thread.id)
                for msg in messages:
                    if msg.role == "assistant" and msg.text_messages:
                        for text_message in msg.text_messages:
                            collected_text.append(text_message.text.value)
                    
                    # Collect URL citations
                    for annotation in msg.url_citation_annotations:
                        if annotation.url_citation:
                            collected_sources.append(annotation.url_citation.url)
                            # Try to extract images from cited URLs if possible
                            if any(ext in annotation.url_citation.url.lower() 
                                  for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                                collected_images.append(annotation.url_citation.url)
            
            # Clean up
            agents_client.delete_agent(agent.id)
            
            return {
                "text": "\n\n".join(collected_text),
                "sources": list(set(collected_sources + urls)),
                "images": collected_images[:3],
                "tables": []
            }
                
        except Exception as e:
            print(f"Bing Custom Search failed: {e}")
            # Fallback to simple HTTP collection
            # return await self._collect_from_urls_simple(urls, topic)
            return {"text": "", "sources": [], "images": [], "tables": []}
    
    async def _search_with_bing(self, title: str, content: str) -> Dict[str, Any]:
        """Bing Search による補足情報収集（Bing Grounding Tool使用）"""
        if not self.bing_tool:
            print("Bing Grounding Tool not available")
            return {"text": "", "sources": [], "images": [], "tables": []}
        
        try:
            # クライアントは既に with ブロック内で開かれている
            agents_client = self.ai_client.agents
            
            # Create agent for Bing search
            agent = agents_client.create_agent(
                model=os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4"),
                name="bing-search-agent",
                instructions="You are a helpful agent that searches for current and accurate information using Bing search. Provide detailed, factual information with sources.",
                tools=self.bing_tool.definitions,
            )
            
            # Create thread for communication
            thread = agents_client.threads.create()
            
            # Create search query
            search_query = f"Find current information about: {title}. Additional context: {content[:200]}"
            
            # Create message
            message = agents_client.messages.create(
                thread_id=thread.id,
                role="user",
                content=search_query,
            )
            
            # Create and process run
            run = agents_client.runs.create_and_process(
                thread_id=thread.id, 
                agent_id=agent.id
            )
            
            # Collect results
            collected_text = []
            collected_sources = []
            collected_images = []
            
            if run.status == "completed":
                # Fetch messages
                messages = agents_client.messages.list(thread_id=thread.id)
                for msg in messages:
                    if msg.role == "assistant" and msg.text_messages:
                        for text_message in msg.text_messages:
                            collected_text.append(text_message.text.value)
                    
                    # Collect URL citations
                    for annotation in msg.url_citation_annotations:
                        if annotation.url_citation:
                            collected_sources.append(annotation.url_citation.url)
                            # Try to extract images from cited URLs if possible
                            if any(ext in annotation.url_citation.url.lower() 
                                  for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                                collected_images.append(annotation.url_citation.url)
            elif run.status == "failed":
                print(f"Bing search run failed: {run.last_error}")
            
            # Clean up
            agents_client.delete_agent(agent.id)
            
            return {
                "text": "\n\n".join(collected_text),
                "sources": collected_sources,
                "images": collected_images[:3],
                "tables": []
            }
                
        except Exception as e:
            print(f"Bing search failed: {e}")
            return {"text": "", "sources": [], "images": [], "tables": []}
    
    def _combine_information(
        self, 
        learn_info: Dict[str, Any], 
        url_info: Dict[str, Any], 
        bing_info: Dict[str, Any]
    ) -> str:
        """収集した情報を統合"""
        combined_text = []
        
        if learn_info.get("text"):
            combined_text.append(learn_info["text"])
        
        if url_info.get("text"):
            combined_text.append(url_info["text"])
        
        if bing_info.get("text"):
            combined_text.append(bing_info["text"])
        
        return "\n\n".join(combined_text)
    
    def _extract_images(self, *info_sources) -> List[str]:
        """画像URLを抽出"""
        images = []
        for source in info_sources:
            if isinstance(source, dict) and "images" in source:
                images.extend(source["images"])
        return images[:5]  # 最大5つの画像
    
    def _extract_tables(self, *info_sources) -> List[Dict[str, Any]]:
        """テーブルデータを抽出"""
        tables = []
        for source in info_sources:
            if isinstance(source, dict) and "tables" in source:
                tables.extend(source["tables"])
        return tables[:2]  # 最大2つのテーブル
    
    def _extract_relevant_content(self, html_content: str, topic: str) -> str:
        """HTMLコンテンツから関連情報を抽出"""
        # 簡単な実装（実際にはBeautifulSoupなどを使用）
        # HTMLタグを除去し、関連するテキストを抽出
        import re
        
        # HTMLタグを除去
        text = re.sub(r'<[^>]+>', '', html_content)
        
        # 改行や空白を整理
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 長すぎる場合は切り詰め
        if len(text) > 1000:
            text = text[:1000] + "..."
        
        return text
    
    def _extract_image_urls(self, html_content: str, base_url: str) -> List[str]:
        """HTMLから画像URLを抽出"""
        import re
        from urllib.parse import urljoin
        
        # img タグのsrc属性を抽出
        img_pattern = r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>'
        matches = re.findall(img_pattern, html_content)
        
        # 絶対URLに変換
        absolute_urls = []
        for url in matches:
            if url.startswith('http'):
                absolute_urls.append(url)
            else:
                absolute_urls.append(urljoin(base_url, url))
        
        return absolute_urls[:3]  # 最大3つの画像

if __name__ == "__main__":
    agent_skills = [
        AgentSkill(
            name="collect_information",
            description="スライドアジェンダに基づいて詳細情報を収集",
            id="collect_information",
            tags=[],
            input_modes=[],
            output_modes=[],
            examples=[]
        )
    ]
        
    # Agent setup
    agent_card = AgentCard(
        name="Information Collection Agent",
        description="Microsoft Learn とWebからの情報収集を行うエージェント",
        version="1.0.0",
        url=settings.information_agent_url,
        skills=agent_skills,
        capabilities={},
        default_input_modes=[],
        default_output_modes=[]
    )

    executor = InformationCollectionExecutor()
    task_store = InMemoryTaskStore()
    request_handler = DefaultRequestHandler(executor, task_store)

    # Create A2A application
    a2a_app = A2AStarletteApplication(agent_card, request_handler)

    uvicorn.run(a2a_app.build(), host="0.0.0.0", port=8002)
