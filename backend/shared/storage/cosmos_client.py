from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity import DefaultAzureCredential
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from ..config import settings

logger = logging.getLogger(__name__)

class CosmosDBClient:
    def __init__(self):
        try:
            credential = DefaultAzureCredential()
            self.client = CosmosClient(settings.cosmos_db_endpoint, credential)
            self._ensure_database()
            self._ensure_containers()
        except Exception as e:
            logger.error(f"Failed to initialize Cosmos DB client: {e}")
            raise
    
    def _ensure_database(self):
        """データベースが存在しない場合は作成"""
        try:
            self.database = self.client.get_database_client(settings.cosmos_db_database_name)
            # Test if database exists by trying to read its properties
            self.database.read()
        except CosmosResourceNotFoundError:
            logger.info(f"Creating database: {settings.cosmos_db_database_name}")
            self.database = self.client.create_database(settings.cosmos_db_database_name)
        except Exception as e:
            logger.error(f"Failed to ensure database: {e}")
            raise

    def _ensure_containers(self):
        """コンテナーが存在しない場合は作成"""
        containers = [
            ("users", "/user_id"),
            ("slide_templates", "/user_id"),
            ("prompt_templates", "/user_id"),
            ("llm_configs", "/user_id"),
            ("slide_jobs", "/user_id"),
            ("generation_history", "/user_id"),
        ]
        
        for container_name, partition_key in containers:
            try:
                container = self.database.get_container_client(container_name)
                # Test if container exists by trying to read its properties
                container.read()
                logger.info(f"Container {container_name} already exists")
            except CosmosResourceNotFoundError:
                logger.info(f"Creating container: {container_name}")
                try:
                    self.database.create_container(
                        id=container_name,
                        partition_key=PartitionKey(path=partition_key)
                    )
                    logger.info(f"Successfully created container: {container_name}")
                except Exception as e:
                    logger.error(f"Failed to create container {container_name}: {e}")
                    raise
            except Exception as e:
                logger.error(f"Failed to check container {container_name}: {e}")
                raise
    
    
    def get_container(self, container_name: str):
        try:
            return self.database.get_container_client(container_name)
        except CosmosResourceNotFoundError:
            logger.error(f"Container {container_name} not found")
            # Try to create the container if it doesn't exist
            self._ensure_containers()
            return self.database.get_container_client(container_name)


    def create_item(self, container_name: str, item: dict) -> dict:
        try:
            container = self.get_container(container_name)
            
            # Ensure 'id' field is present
            if 'id' not in item or not item['id']:
                raise ValueError("Item must have an 'id' field")
            
            return container.create_item(body=item)
        except Exception as e:
            print(f"Failed to create item in {container_name}: {e}")
            raise
    
    def get_item(self, container_name: str, item_id: str, partition_key: str = None) -> dict:
        try:
            container = self.get_container(container_name)
            if partition_key is None:
                partition_key = item_id
            return container.read_item(item=item_id, partition_key=partition_key)
        except Exception as e:
            print(f"Failed to get item {item_id} from {container_name}: {e}")
            raise

    def read_item(self, container_name: str, item_id: str, partition_key: str) -> Optional[Dict[str, Any]]:
        try:
            container = self.get_container(container_name)
            return container.read_item(item=item_id, partition_key=partition_key)
        except CosmosResourceNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Failed to read item from {container_name}: {e}")
            raise
    
    def update_item(self, container_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
        try:
            container = self.get_container(container_name)
            item["updated_at"] = datetime.utcnow().isoformat()
            return container.replace_item(item=item["id"], body=item)
        except Exception as e:
            logger.error(f"Failed to update item in {container_name}: {e}")
            raise
    
    def delete_item(self, container_name: str, item_id: str, partition_key: str):
        try:
            container = self.get_container(container_name)
            container.delete_item(item=item_id, partition_key=partition_key)
        except Exception as e:
            logger.error(f"Failed to delete item from {container_name}: {e}")
            raise
    
    def query_items(self, container_name: str, query: str, parameters: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        try:
            container = self.get_container(container_name)
            items = list(container.query_items(
                query=query,
                parameters=parameters or [],
                enable_cross_partition_query=True
            ))
            return items
        except CosmosResourceNotFoundError:
            logger.warning(f"Container {container_name} not found, returning empty list")
            return []
        except Exception as e:
            logger.error(f"Failed to query items from {container_name}: {e}")
            raise
    
    def get_user_items(self, container_name: str, user_id: str) -> List[Dict[str, Any]]:
        try:
            query = "SELECT * FROM c WHERE c.user_id = @user_id ORDER BY c.created_at DESC"
            parameters = [{"name": "@user_id", "value": user_id}]
            return self.query_items(container_name, query, parameters)
        except Exception as e:
            logger.error(f"Failed to get user items from {container_name}: {e}")
            return []

# Global instance
cosmos_client = CosmosDBClient()
