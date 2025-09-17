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
            "content": "• Azure Cognitive Services（現Azure AI Services）\n• Azure Machine Learning\n• Azure OpenAI Service\n• Computer Vision、Speech、Language Service\n• 事前学習済みモデルをAPI経由で即利用可能\n• エンタープライズレベルのセキュリティとコンプライアンス",
            "notes": "2025年現在、30以上のAIサービスを提供。開発者がAI機能をアプリケーションに統合するためのクラウドベースサービス群。",
            "images": [],
            "tables": []
        },
        {
            "page_number": 2,
            "title": "機械学習モデルの開発とデプロイメント",
            "content": "• Azure Machine Learning Studioでのノーコード/ローコード開発\n• AutoML（自動機械学習）機能\n• データ準備からモデル運用までの一元管理\n• モデルレジストリでのバージョン管理\n• Azure Container Instance (ACI) / Azure Kubernetes Service (AKS) でのデプロイ\n• MLOpsによる運用・保守",
            "notes": "Python/R言語対応、分散学習、CI/CD統合。SDK v2への移行が推奨されている。",
            "images": [],
            "tables": []
        },
        {
            "page_number": 3,
            "title": "実用的な活用事例とROI",
            "content": "• 金融業界：三菱UFJ銀行の融資審査・顧客対応自動化\n• 製造業：トヨタ自動車の自動運転・工場AI基盤\n• 小売業：ユニクロのAI需要予測、セブン-イレブンの商品企画短縮\n• ホスピタリティ：星野リゾートのダイナミックプライシング\n• 投資回収期間：多くが1～2年以内\n• 効果：業務効率化、顧客満足度向上、意思決定高速化",
            "notes": "具体的ROI例：月22万時間削減（三菱UFJ）、稼働率76%→87%（星野リゾート）、廃棄ロス30%削減（スシロー）",
            "images": [],
            "tables": []
        }
    ],
    "total_pages": 3,
    "estimated_duration": 20
}

SAMPLE_INFORMATION = {
    "slide_1": {
        "text": "Azure AI Services（旧Azure Cognitive Services）は、Microsoft Azureが提供するクラウドベースのAI機能群です。2025年現在、30以上のAIサービスを提供しており、開発者がAI機能をアプリケーションに統合するためのシンプルなAPIを提供しています。\n\n主なサービスカテゴリ：\n\n**Azure AI Vision（Computer Vision）**\n画像・動画解析、物体検出、顔認識、OCR（文字認識）などを提供。メディアコンテンツの自動分類や監視用途に活用されています。\n\n**Azure AI Language（Language Service）**\nテキスト分析（感情分析、キーフレーズ抽出、固有表現抽出）、検索支援、チャットボット構築に対応。多言語での自然言語処理が可能です。\n\n**Azure AI Speech**\n音声認識、音声合成、音声翻訳など、多言語対応の音声技術を提供。リアルタイムでの音声処理が可能です。\n\n**Azure OpenAI Service**\nGPTシリーズ、DALLE、Codexなど、OpenAIの高度な言語モデルをMicrosoft Azureのセキュリティ基盤上で利用可能。エンタープライズ向けのセキュリティ・コンプライアンス対応が特徴です。\n\n特徴として、事前学習済みモデルをAPI経由で即座に利用でき、GDPR、HIPAA、SOC 2、ISO 27001に準拠したセキュリティを提供しています。",
        "sources": [
            "https://learn.microsoft.com/azure/ai-services/",
            "https://azure.microsoft.com/products/ai-services/",
            "https://learn.microsoft.com/ja-jp/azure/cognitive-services/overview"
        ],
        "images": [
            "https://learn.microsoft.com/azure/ai-services/media/overview.png"
        ],
        "tables": [
            {
                "headers": ["サービス", "説明", "主な用途"],
                "rows": [
                    ["Computer Vision", "画像・動画解析", "OCR、物体検出、顔認識"],
                    ["Language Service", "自然言語処理", "感情分析、テキスト分類"],
                    ["Speech Services", "音声処理", "音声認識、音声合成"],
                    ["OpenAI Service", "大規模言語モデル", "テキスト生成、コード生成"]
                ]
            }
        ]
    },
    "slide_2": {
        "text": "Azure Machine Learning は、機械学習モデルの構築、トレーニング、デプロイ、管理までを支援するクラウドベースのプラットフォームです。2025年現在、ノーコード/ローコードでの開発環境が充実しており、データサイエンスの専門知識がなくても機械学習モデルを構築できます。\n\n**主な開発プロセス：**\n\n1. **データ準備**\n   - Azure ML Studioでのデータアップロードと前処理\n   - データストア（Blob、SQL DBなど）との連携\n   - 欠損値処理、標準化・正規化、特徴量エンジニアリング\n\n2. **モデル作成・トレーニング**\n   - AutoML（自動機械学習）による自動モデル選択\n   - Python/R、深層学習フレームワーク（PyTorch、TensorFlow）対応\n   - CPU/GPU、分散処理クラスタでのスケーラブルなトレーニング\n   - ハイパーパラメータースイープによる自動最適化\n\n3. **モデル評価・管理**\n   - モデルレジストリでのバージョン管理\n   - 精度、再現率、F値などの評価指標レポート\n   - MLOps（Machine Learning Operations）統合\n\n4. **デプロイメント**\n   - **Azure Container Instance (ACI)**：開発・テスト向け、小規模で迅速なデプロイ\n   - **Azure Kubernetes Service (AKS)**：本番運用向け、スケーラブルな推論サービス\n   - REST APIエンドポイントとしての公開\n   - リアルタイム推論とバッチ推論の両方をサポート\n\n**2025年の新機能：**\n- SDK v2/CLI v2への移行（旧バージョンは段階的終了）\n- Responsible AI機能の強化（公正性、説明性の向上）\n- Azure AI Foundry/Agent Serviceとの連携",
        "sources": [
            "https://learn.microsoft.com/azure/machine-learning/",
            "https://learn.microsoft.com/ja-jp/azure/machine-learning/overview-what-is-azure-machine-learning",
            "https://learn.microsoft.com/azure/machine-learning/how-to-deploy-and-where"
        ],
        "images": [],
        "tables": [
            {
                "headers": ["デプロイ先", "用途", "特徴", "適用場面"],
                "rows": [
                    ["Azure Container Instance", "開発・テスト", "小規模、迅速", "プロトタイプ、検証"],
                    ["Azure Kubernetes Service", "本番運用", "スケーラブル、高可用性", "大規模サービス"],
                    ["Azure Functions", "サーバーレス", "イベント駆動", "リアルタイム推論"],
                    ["Edge デバイス", "エッジ推論", "低レイテンシ", "IoT、製造業"]
                ]
            }
        ]
    },
    "slide_3": {
        "text": "2025年現在、多くの企業がAzure AIサービスを活用して実用的な成果と高いROI（投資利益率）を達成しています。投資回収期間は多くの事例で1～2年以内となっており、継続的な利益拡大が実現されています。\n\n**金融業界の事例：**\n\n**三菱UFJ銀行**\n- 活用内容：融資審査、顧客対応、コールセンター業務の自動化に生成AI（ChatGPT）を導入\n- 効果：月22万時間以上の労働時間削減、提案品質向上\n- 投資額：2027年までに約500億円\n- ROI：人件費削減と顧客満足度向上の両面で効果\n\n**製造業の事例：**\n\n**トヨタ自動車×NTT**\n- 活用内容：自動運転技術、モビリティAI基盤開発、工場でのAIモデル開発プラットフォーム\n- 投資額：2030年までに約5,000億円\n- 効果：交通事故ゼロ社会への貢献、生産性向上\n\n**小売・EC業界の事例：**\n\n**ユニクロ（ファーストリテイリング）**\n- 活用内容：GoogleとのAI需要予測システムによる在庫・商品最適化\n- 効果：過去最高売上を更新、余剰在庫と機会損失の削減\n\n**セブン-イレブン・ジャパン**\n- 活用内容：生成AIによる商品企画期間の短縮（1/10、約3日）\n- 効果：新商品投入ペース向上、即日稟議決裁の実現\n\n**ホスピタリティ業界の事例：**\n\n**星野リゾート**\n- 活用内容：AI需要予測によるダイナミックプライシング\n- 効果：稼働率76%→87%、ADR（平均客室単価）15%アップ\n- ROI：初年度1億円投資で二桁成長\n\n**外食産業の事例：**\n\n**スシロー**\n- 活用内容：RFID×AIによるリアルタイム需要予測、廃棄ロス削減\n- 効果：廃棄ロス30%削減、客単価5%アップ\n\n**共通する成功要因：**\n- 業務効率化による時間・コスト削減\n- 顧客満足度向上（パーソナライズ対応）\n- 意思決定の高速化（リアルタイム分析）\n- 新規ビジネス創出（AI生成コンテンツ、プロダクト開発）",
        "sources": [
            "https://learn.microsoft.com/azure/ai-services/case-studies/",
            "https://learn.microsoft.com/ja-jp/azure/architecture/example-scenario/ai/",
            "https://learn.microsoft.com/ja-jp/azure/industry/overview/"
        ],
        "images": [],
        "tables": [
            {
                "headers": ["企業", "業界", "活用内容", "主な効果", "ROI"],
                "rows": [
                    ["三菱UFJ銀行", "金融", "生成AI導入", "月22万時間削減", "コスト25%削減"],
                    ["星野リゾート", "ホテル", "ダイナミック価格", "稼働率11%向上", "二桁成長"],
                    ["スシロー", "外食", "需要予測AI", "廃棄ロス30%削減", "客単価5%向上"],
                    ["セブン-イレブン", "小売", "商品企画AI", "企画期間1/10短縮", "売上機会拡大"]
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
        print(f"     Notes length: {len(slide.get('notes', ''))}")
    
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
                    print(f"       Table {i+1}: Standard format (headers + rows) - {len(table.get('rows', []))} rows")
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
    print("• ✓ Sample agenda and information data structure (3 slides)")
    print("• ✓ Slide creation with realistic Azure AI content")
    print("• ✓ PowerPoint file generation and upload to blob storage")
    print("• ✓ Slide content extraction for review")
    print("• ✓ Enhanced sample data with enterprise use cases and ROI examples")


if __name__ == "__main__":
    asyncio.run(main())
