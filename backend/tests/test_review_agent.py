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


async def test_review_agent():
    """Test review agent using A2A client"""
    
    print("=== Testing Review Agent ===")
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    review_agent_url = "http://localhost:8004"
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as httpx_client:
        try:
            # Test basic connectivity
            print(f"1. Testing connectivity to {review_agent_url}...")
            response = await httpx_client.get(f"{review_agent_url}/")
            print(f"   ✓ Agent is responding (status: {response.status_code})")
            
            # Test agent card endpoint
            print(f"2. Fetching agent card...")
            card_url = f"{review_agent_url}{AGENT_CARD_WELL_KNOWN_PATH}"
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
                base_url=review_agent_url,
            )
            
            agent_card = await resolver.get_agent_card()
            clientconfig = ClientConfig(
                httpx_client=httpx_client
            )
            clientfactory = ClientFactory(clientconfig)
            client = clientfactory.create(
                card=agent_card
            )
            
            # Prepare test request with sample slide data
            print(f"4. Sending slide review request...")
            
            # Sample agenda that would have been used to create the slide
            test_agenda = {
                "title": "Azure AI サービスと機械学習",
                "total_pages": 3,
                "slides": [
                    {
                        "page_number": 1,
                        "title": "Azure AI サービス概要",
                        "content": "Azure Cognitive Services、Azure Machine Learning、Azure OpenAI Service の概要"
                    },
                    {
                        "page_number": 2,
                        "title": "機械学習モデルの開発",
                        "content": "Azure ML Studio を使用したモデル開発とデプロイメント"
                    },
                    {
                        "page_number": 3,
                        "title": "実用的な活用事例",
                        "content": "企業での AI サービス活用事例と ROI"
                    }
                ]
            }
            
            # Sample slide contents that would be extracted from actual PowerPoint
            test_slide_contents = [
                {
                    "slide_number": 1,
                    "title": "Azure AI サービス概要",
                    "planned_content": "Azure Cognitive Services、Azure Machine Learning、Azure OpenAI Service の概要",
                    "actual_text": "Azure AI サービス概要\n\nAzure Cognitive Services は画像認識、音声認識、自然言語処理を提供\nAzure Machine Learning は機械学習モデルの開発・デプロイ環境\nAzure OpenAI Service は GPT-4、ChatGPT などの大規模言語モデルへのアクセス",
                    "images": [{"type": "image", "description": "Azure AI サービスのアーキテクチャ図"}],
                    "tables": [],
                    "shape_count": 5
                },
                {
                    "slide_number": 2,
                    "title": "機械学習モデルの開発",
                    "planned_content": "Azure ML Studio を使用したモデル開発とデプロイメント",
                    "actual_text": "機械学習モデルの開発\n\nAzure ML Studio の主要機能:\n• ドラッグ&ドロップでのパイプライン設計\n• 自動機械学習 (AutoML)\n• モデルの版管理とデプロイメント\n• リアルタイム推論エンドポイント",
                    "images": [],
                    "tables": [
                        {
                            "type": "table",
                            "data": [
                                ["機能", "説明", "利用シーン"],
                                ["AutoML", "自動でモデル選択・調整", "初心者向け"],
                                ["Designer", "ビジュアルパイプライン", "プロトタイプ"],
                                ["Notebooks", "Jupyter環境", "カスタム開発"]
                            ]
                        }
                    ],
                    "shape_count": 4
                },
                {
                    "slide_number": 3,
                    "title": "実用的な活用事例",
                    "planned_content": "企業での AI サービス活用事例と ROI",
                    "actual_text": "実用的な活用事例\n\n製造業: 品質検査の自動化 - 99.8% の精度で不良品検出\n小売業: 需要予測システム - 在庫コスト 15% 削減\n金融業: 不正検知システム - 偽陽性率 50% 改善\n\nROI実績: 平均 6ヶ月で投資回収、年間 25% のコスト削減効果",
                    "images": [{"type": "image", "description": "ROI グラフ"}],
                    "tables": [],
                    "shape_count": 6
                }
            ]
            # Slide URL を環境変数等で設定しておく
            test_review_agent_slide_url = ""
            if test_review_agent_slide_url == "":
                print(f"   ✗ test_review_agent_slide_url is not set in config")
                return

            # Test payload for review agent
            test_payload = {
                "slide_url": test_review_agent_slide_url,
                "agenda": test_agenda,
                "slide_contents": test_slide_contents
            }

            # Create proper A2A Parts
            data_part = Part(root=DataPart(
                data={
                    "skill": "review_slides",
                    "request_id": str(uuid.uuid4()),
                    "agent_type": "review_slides",
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
                
                # Try to extract result from the final response
                if hasattr(final_response, 'result') and final_response.result:
                    result = final_response.result
                    if isinstance(result, dict):
                        print(f"\n✓ Slide review completed:")
                        
                        # Display overall score
                        overall_score = result.get('overall_score', 'N/A')
                        print(f"   Overall Score: {overall_score}")
                        
                        # Display quality checks
                        quality_checks = result.get('quality_checks', {})
                        if quality_checks:
                            print(f"   Quality Checks:")
                            for check_name, score in quality_checks.items():
                                print(f"      {check_name}: {score}")
                        
                        # Display issues
                        issues = result.get('issues', [])
                        if issues:
                            print(f"   Issues Found ({len(issues)}):")
                            for issue in issues:
                                slide_num = issue.get('slide_number', 'N/A')
                                issue_type = issue.get('type', 'N/A')
                                severity = issue.get('severity', 'N/A')
                                description = issue.get('description', 'N/A')
                                print(f"      Slide {slide_num}: [{severity}] {issue_type} - {description}")
                        else:
                            print(f"   No issues found")
                        
                        # Display recommendations
                        recommendations = result.get('recommendations', [])
                        if recommendations:
                            print(f"   Recommendations ({len(recommendations)}):")
                            for i, rec in enumerate(recommendations, 1):
                                print(f"      {i}. {rec}")
                        
                        # Display notes for slides
                        notes_for_slides = result.get('notes_for_slides', {})
                        if notes_for_slides:
                            print(f"   Notes for specific slides:")
                            for slide_num, note in notes_for_slides.items():
                                print(f"      Slide {slide_num}: {note}")
                        
                    else:
                        print(f"   Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
                else:
                    # Try to get data from response attributes
                    if hasattr(final_response, 'model_dump'):
                        response_data = final_response.model_dump(mode='json', exclude_none=True)
                        print(f"   Full response: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
                    elif hasattr(final_response, '__dict__'):
                        print(f"   Response attributes: {final_response.__dict__}")
                    else:
                        print(f"   Raw response: {final_response}")
            else:
                print("   No responses received from generator")
                
        except Exception as e:
            print(f"✗ Test failed: {str(e)}")
            import traceback
            traceback.print_exc()


async def main():
    """Run review agent tests"""
    print("Testing Review Agent Communication")
    print("=" * 50)
    
    await test_review_agent()
    
    print("\n" + "=" * 50)
    print("Test completed")


if __name__ == "__main__":
    asyncio.run(main())
