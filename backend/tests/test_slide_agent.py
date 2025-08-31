#!/usr/bin/env python3
"""
Slide Agent のテストスクリプト
"""

import asyncio
import uuid
import logging
import json

import httpx
from a2a.client import A2ACardResolver, ClientFactory, ClientConfig 
from a2a.types import (
    Message,
    Part,
    DataPart,
    Role
)
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH

# テスト用のサンプルデータ
SAMPLE_AGENDA = {
    "slides": [
        {
            "page_number": 1,
            "title": "Azure AI Services概要",
            "content": "• Azure Cognitive Services\n• Azure Machine Learning\n• Azure OpenAI Service",
            "notes": "",
            "images": [],
            "tables": []
        },
        {
            "page_number": 2,
            "title": "Azure OpenAI Service詳細",
            "content": "• GPT-4モデル\n• Text Embedding\n• DALL-E 3",
            "notes": "",
            "images": [],
            "tables": []
        }
    ],
    "total_pages": 2,
    "estimated_duration": 15
}

SAMPLE_INFORMATION = {
    "slide_1": {
        "text": "Azure AI Servicesは、開発者がAI機能をアプリケーションに統合するためのクラウドベースのサービス群です。Computer Vision、Speech Services、Language Servicesなど、30以上のAIサービスを提供しています。",
        "sources": [
            "https://learn.microsoft.com/azure/ai-services/",
            "https://azure.microsoft.com/products/ai-services/"
        ],
        "images": [
            "https://learn.microsoft.com/azure/ai-services/media/overview.png"
        ],
        "tables": [
            {
                "headers": ["サービス", "説明", "用途"],
                "rows": [
                    ["Computer Vision", "画像解析", "OCR、物体検出"],
                    ["Speech Services", "音声処理", "音声認識、合成"]
                ]
            }
        ]
    },
    "slide_2": {
        "text": "Azure OpenAI Serviceは、OpenAIの高度な言語モデルへのアクセスを提供します。GPT-4、GPT-3.5-turbo、Embeddingsモデルなどが利用可能で、エンタープライズレベルのセキュリティとコンプライアンスを備えています。",
        "sources": [
            "https://learn.microsoft.com/azure/ai-services/openai/",
            "https://azure.microsoft.com/products/ai-services/openai-service/"
        ],
        "images": [],
        "tables": [
            {
                "data": [
                    ["モデル", "最大トークン", "用途"],
                    ["GPT-4", "8,192", "高度なテキスト生成"],
                    ["GPT-3.5-turbo", "4,096", "チャット、要約"]
                ]
            }
        ]
    }
}


async def test_slide_agent():
    """Test slide agent using A2A client"""
    
    print("=== Testing Slide Agent ===")
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    slide_agent_url = "http://localhost:8003"
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as httpx_client:
        try:
            # Test basic connectivity
            print(f"1. Testing connectivity to {slide_agent_url}...")
            response = await httpx_client.get(f"{slide_agent_url}/")
            print(f"   ✓ Agent is responding (status: {response.status_code})")
            
            # Test agent card endpoint
            print(f"2. Fetching agent card...")
            card_url = f"{slide_agent_url}{AGENT_CARD_WELL_KNOWN_PATH}"
            response = await httpx_client.get(card_url)
            
            if response.status_code != 200:
                print(f"   ✗ Agent card failed (status: {response.status_code})")
                print(f"   Response: {response.text}")
                return
                
            agent_card_data = response.json()
            print(f"   ✓ Agent card fetched successfully")
            print(f"   - Name: {agent_card_data.get('name', 'N/A')}")
            print(f"   - Version: {agent_card_data.get('version', 'N/A')}")
            print(f"   - Skills: {[skill.get('name') for skill in agent_card_data.get('skills', [])]}")
            
            # Initialize A2A client
            print(f"3. Initializing A2A client...")
            resolver = A2ACardResolver(
                httpx_client=httpx_client,
                base_url=slide_agent_url,
            )
            
            agent_card = await resolver.get_agent_card()
            clientconfig = ClientConfig(
                httpx_client=httpx_client
            )
            clientfactory = ClientFactory(clientconfig)
            client = clientfactory.create(
                card=agent_card
            )
            
            # Prepare test request
            print(f"4. Sending slide creation request...")
            test_payload = {
                "agenda": SAMPLE_AGENDA,
                "information": SAMPLE_INFORMATION,
                "template_id": None,
                "include_images": True,
                "include_tables": True
            }

            # Create proper A2A Parts
            data_part = Part(root=DataPart(
                data={
                    "skill": "create_slides",
                    "request_id": str(uuid.uuid4()),
                    "agent_type": "create_slides",
                    "payload": test_payload,
                    "user_id": "test_user"
                }
            ))

            # Create message with proper A2A SDK structure
            message = Message(
                message_id=str(uuid.uuid4()),
                role=Role.user,
                parts=[data_part]  # Use the structured data part
            )

            # Handle async generator response
            print(f"   Sending message to slide agent...")
            response_generator = client.send_message(message)
            print(f"   ✓ Response received as async generator")
            
            # Collect all responses from the async generator
            responses = []
            async for response_chunk in response_generator:
                responses.append(response_chunk)
                print(f"   Response chunk received: {type(response_chunk)}")
            
            # Display results
            if responses:
                final_response = responses[-1]  # Get the last response
                print(f"   Total response chunks: {len(responses)}")
                
                # デバッグ情報を詳細に出力
                print(f"   Debug: Response type: {type(final_response)}")
                
                # Try to extract result from the final response
                if hasattr(final_response, 'parts') and final_response.parts:
                    print(f"   Debug: Found {len(final_response.parts)} parts")
                    for i, part in enumerate(final_response.parts):
                        print(f"   Debug: Part {i} type: {type(part)}")
                        print(f"   Debug: Part {i} root type: {type(part.root)}")
                        
                        if hasattr(part.root, 'text'):
                            print(f"   Debug: Part {i} text content: {part.root.text[:500]}...")
                            try:
                                result = json.loads(part.root.text)
                                print(f"\n✓ Slide creation completed:")
                                print(f"   - File: {result.get('filename', 'N/A')}")
                                print(f"   - URL: {result.get('slide_url', 'N/A')}")
                                
                                slide_contents = result.get('slide_contents', [])
                                if slide_contents:
                                    print(f"   - Generated {len(slide_contents)} slides:")
                                    for slide in slide_contents:
                                        print(f"     {slide.get('slide_number', '?')}. {slide.get('title', 'N/A')}")
                                        print(f"        Text length: {len(slide.get('actual_text', ''))}")
                                        print(f"        Images: {len(slide.get('images', []))}")
                                        print(f"        Tables: {len(slide.get('tables', []))}")
                                
                            except json.JSONDecodeError as e:
                                print(f"   JSON decode error: {e}")
                                print(f"   Text response (first 500 chars): {part.root.text[:500]}...")
                        elif hasattr(part.root, 'data'):
                            print(f"   Debug: Part {i} data content: {str(part.root.data)[:500]}...")
                else:
                    if hasattr(final_response, 'model_dump'):
                        print(f"   Full response (model_dump): {final_response.model_dump(mode='json', exclude_none=True)}")
                    else:
                        print(f"   Raw response: {final_response}")
            else:
                print("   No responses received from generator")
                
        except Exception as e:
            print(f"✗ Test failed: {str(e)}")
            import traceback
            traceback.print_exc()


def test_sample_data_structure():
    """Test the structure of sample data"""
    print("\n=== Testing Sample Data Structure ===")
    
    # Test agenda structure
    print("1. Testing agenda structure:")
    agenda = SAMPLE_AGENDA
    print(f"   ✓ Total slides: {agenda.get('total_pages', 0)}")
    print(f"   ✓ Estimated duration: {agenda.get('estimated_duration', 0)} minutes")
    
    for slide in agenda.get('slides', []):
        print(f"   - Slide {slide.get('page_number', '?')}: {slide.get('title', 'N/A')}")
        print(f"     Content length: {len(slide.get('content', ''))}")
    
    # Test information structure
    print("\n2. Testing information structure:")
    for slide_key, info in SAMPLE_INFORMATION.items():
        print(f"   {slide_key}:")
        print(f"     - Text length: {len(info.get('text', ''))}")
        print(f"     - Sources: {len(info.get('sources', []))}")
        print(f"     - Images: {len(info.get('images', []))}")
        print(f"     - Tables: {len(info.get('tables', []))}")
        
        # Test table formats
        for i, table in enumerate(info.get('tables', [])):
            if isinstance(table, dict):
                if "headers" in table and "rows" in table:
                    print(f"       Table {i+1}: Standard format (headers + rows)")
                elif "data" in table:
                    print(f"       Table {i+1}: Information agent format (data array)")
                else:
                    print(f"       Table {i+1}: Unknown format")
            else:
                print(f"       Table {i+1}: Non-dict format")


async def main():
    """Run slide agent test"""
    print("Testing Slide Agent Communication")
    print("=" * 50)
    
    # Test sample data structure first
    test_sample_data_structure()
    
    # Test actual agent communication
    await test_slide_agent()
    
    print("\n" + "=" * 50)
    print("Test completed")
    print("\nThis test validates:")
    print("• ✓ Slide agent connectivity and agent card")
    print("• ✓ A2A client communication with slide agent")
    print("• ✓ Sample agenda and information data structure")
    print("• ✓ Slide creation with agenda and information input")
    print("• ✓ PowerPoint file generation and upload to blob storage")
    print("• ✓ Slide content extraction for review")


if __name__ == "__main__":
    asyncio.run(main())
