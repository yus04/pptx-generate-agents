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


async def test_agenda_agent():
    """Test agenda agent using A2A client"""
    
    print("=== Testing Agenda Agent ===")
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    agenda_agent_url = "http://localhost:8001"
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as httpx_client:
        try:
            # Test basic connectivity
            print(f"1. Testing connectivity to {agenda_agent_url}...")
            response = await httpx_client.get(f"{agenda_agent_url}/")
            print(f"   ✓ Agent is responding (status: {response.status_code})")
            
            # Test agent card endpoint
            print(f"2. Fetching agent card...")
            card_url = f"{agenda_agent_url}{AGENT_CARD_WELL_KNOWN_PATH}"
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
                base_url=agenda_agent_url,
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
            print(f"4. Sending agenda generation request...")
            test_payload = {
                "prompt": "Azure AI サービスと機械学習についてのプレゼンテーション",
                "max_slides": 5,
                "reference_urls": ["https://learn.microsoft.com/azure/ai-services/"]
            }

            # Create proper A2A Parts
            data_part = Part(root=DataPart(
                data={
                    "skill": "generate_agenda",
                    "request_id": str(uuid.uuid4()),
                    "agent_type": "generate_agenda",
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
                    if isinstance(result, dict) and 'slides' in result:
                        slides = result.get('slides', [])
                        total_pages = result.get('total_pages', len(slides))
                        print(f"\n✓ Generated agenda with {total_pages} slides:")
                        for slide in slides:
                            print(f"   {slide.get('page_number', '?')}. {slide.get('title', 'N/A')}")
                            print(f"      {slide.get('content', '')[:100]}...")
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
    """Run agenda agent test"""
    print("Testing Agenda Agent Communication")
    print("=" * 50)
    
    await test_agenda_agent()
    
    print("\n" + "=" * 50)
    print("Test completed")


if __name__ == "__main__":
    asyncio.run(main())
