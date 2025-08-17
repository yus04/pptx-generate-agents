from fastapi import FastAPI
from azure.ai.projects import AIProjectsClient
from azure.ai.projects.models import AgentRunRequest
from azure.identity import DefaultAzureCredential
from typing import Dict, Any, List
import httpx
import json

from a2a_python_sdk import (
    AgentCard, AgentSkill, AgentExecutor, DefaultRequestHandler,
    A2AStarletteApplication
)

from ...shared.models import AgentRequest, AgentResponse
from ...shared.config import settings


class InformationCollectionExecutor(AgentExecutor):
    def __init__(self):
        self.ai_client = AIProjectsClient(
            endpoint=settings.azure_ai_foundry_endpoint,
            credential=DefaultAzureCredential()
        )
    
    async def execute(self, request: AgentRequest) -> AgentResponse:
        """情報収集を実行"""
        try:
            payload = request.payload
            agenda = payload.get("agenda", {})
            reference_urls = payload.get("reference_urls", [])
            
            if not agenda:
                return AgentResponse(
                    request_id=request.request_id,
                    success=False,
                    error="Agenda is required"
                )
            
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
            
            return AgentResponse(
                request_id=request.request_id,
                success=True,
                result=collected_info
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
    
    async def _collect_slide_information(
        self, 
        title: str, 
        content: str, 
        reference_urls: List[str]
    ) -> Dict[str, Any]:
        """個別スライドの情報を収集"""
        
        # Microsoft Learn MCP Server を使用した情報収集
        learn_info = await self._search_microsoft_learn(title, content)
        
        # 参照URLからの情報収集
        url_info = await self._collect_from_urls(reference_urls, title)
        
        # Bing Search を使用した補足情報
        bing_info = await self._search_with_bing(title, content)
        
        return {
            "text": self._combine_information(learn_info, url_info, bing_info),
            "images": self._extract_images(learn_info, url_info),
            "tables": self._extract_tables(learn_info, url_info),
            "sources": reference_urls + learn_info.get("sources", [])
        }
    
    async def _search_microsoft_learn(self, title: str, content: str) -> Dict[str, Any]:
        """Microsoft Learn からの情報検索"""
        try:
            # Azure AI Foundry Agent Service を使用
            search_query = f"{title} {content}"
            
            # TODO: Implement actual Microsoft Learn MCP Server call
            # For now, return mock data
            return {
                "text": f"Microsoft Learn での検索結果: {title}に関する詳細情報",
                "sources": ["https://learn.microsoft.com/example"],
                "images": [],
                "tables": []
            }
        except Exception as e:
            print(f"Microsoft Learn search failed: {e}")
            return {"text": "", "sources": [], "images": [], "tables": []}
    
    async def _collect_from_urls(self, urls: List[str], topic: str) -> Dict[str, Any]:
        """指定されたURLからの情報収集"""
        collected_text = []
        collected_images = []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for url in urls:
                try:
                    if not url.strip():
                        continue
                        
                    response = await client.get(url)
                    if response.status_code == 200:
                        # 簡単なテキスト抽出（実際にはより高度なスクレイピングが必要）
                        content = response.text
                        # TODO: Implement proper content extraction
                        extracted = self._extract_relevant_content(content, topic)
                        collected_text.append(extracted)
                        
                        # 画像URL抽出
                        images = self._extract_image_urls(content, url)
                        collected_images.extend(images)
                        
                except Exception as e:
                    print(f"Failed to collect from {url}: {e}")
                    continue
        
        return {
            "text": "\n\n".join(collected_text),
            "sources": [url for url in urls if url.strip()],
            "images": collected_images[:3],  # 最大3つの画像
            "tables": []
        }
    
    async def _search_with_bing(self, title: str, content: str) -> Dict[str, Any]:
        """Bing Search による補足情報収集"""
        try:
            # Azure Cognitive Services Bing Search API
            # TODO: Implement actual Bing Search API call
            return {
                "text": f"Bing検索での補足情報: {title}",
                "sources": [],
                "images": [],
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


# Agent setup
agent_card = AgentCard(
    name="Information Collection Agent",
    description="Microsoft Learn とWebからの情報収集を行うエージェント",
    version="1.0.0"
)

agent_skills = [
    AgentSkill(
        name="collect_information",
        description="スライドアジェンダに基づいて詳細情報を収集"
    )
]

executor = InformationCollectionExecutor()
request_handler = DefaultRequestHandler(agent_card, agent_skills, executor)

# FastAPI app
app = FastAPI(title="Information Collection Agent")

# Create A2A application
a2a_app = A2AStarletteApplication(app, request_handler)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(a2a_app, host="0.0.0.0", port=8002)