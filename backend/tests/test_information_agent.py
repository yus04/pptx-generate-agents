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


async def test_information_agent():
    """Test information agent using A2A client"""
    
    print("=== Testing Information Agent ===")
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    information_agent_url = "http://localhost:8002"
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as httpx_client:
        try:
            # Test basic connectivity
            print(f"1. Testing connectivity to {information_agent_url}...")
            response = await httpx_client.get(f"{information_agent_url}/")
            print(f"   ✓ Agent is responding (status: {response.status_code})")
            
            # Test agent card endpoint
            print(f"2. Fetching agent card...")
            card_url = f"{information_agent_url}{AGENT_CARD_WELL_KNOWN_PATH}"
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
                base_url=information_agent_url,
            )
            
            agent_card = await resolver.get_agent_card()
            clientconfig = ClientConfig(
                httpx_client=httpx_client
            )
            clientfactory = ClientFactory(clientconfig)
            client = clientfactory.create(
                card=agent_card
            )
            
            # Prepare test request with sample agenda
            print(f"4. Sending information collection request...")
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
            
            test_payload = {
                "agenda": test_agenda,
                "reference_urls": [
                    "https://learn.microsoft.com/azure/ai-services/",
                    "https://learn.microsoft.com/azure/machine-learning/"
                ]
            }

            # Create proper A2A Parts
            data_part = Part(root=DataPart(
                data={
                    "skill": "collect_information",
                    "request_id": str(uuid.uuid4()),
                    "agent_type": "collect_information",
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
                        print(f"\n✓ Information collection completed:")
                        for slide_key, slide_info in result.items():
                            print(f"   {slide_key}:")
                            if isinstance(slide_info, dict):
                                text_preview = slide_info.get('text', '')[:150]
                                sources_count = len(slide_info.get('sources', []))
                                images_count = len(slide_info.get('images', []))
                                tables_count = len(slide_info.get('tables', []))
                                print(f"      Text preview: {text_preview}...")
                                print(f"      Sources: {sources_count}, Images: {images_count}, Tables: {tables_count}")
                            else:
                                print(f"      {slide_info}")
                    else:
                        print(f"   Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
                else:
                    # Try to get data from response attributes
                    if hasattr(final_response, 'model_dump'):
                        print(f"   Full response: {final_response.model_dump(mode='json', exclude_none=True)}")
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
    """Run information agent tests"""
    print("Testing Information Agent Communication")
    print("=" * 50)
    
    await test_information_agent()
    
    print("\n" + "=" * 50)
    print("Test completed")


if __name__ == "__main__":
    asyncio.run(main())
