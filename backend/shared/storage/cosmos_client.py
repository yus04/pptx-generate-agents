from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from typing import Dict, Any, List, Optional
import json
from datetime import datetime

from ..config import settings


class CosmosDBClient:
    def __init__(self):
        self.client = CosmosClient(settings.cosmos_db_endpoint, settings.cosmos_db_key)
        self.database = self.client.get_database_client(settings.cosmos_db_database_name)
        self._ensure_containers()
    
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
                self.database.get_container_client(container_name)
            except CosmosResourceNotFoundError:
                self.database.create_container(
                    id=container_name,
                    partition_key=PartitionKey(path=partition_key)
                )
    
    def get_container(self, container_name: str):
        return self.database.get_container_client(container_name)
    
    def create_item(self, container_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
        container = self.get_container(container_name)
        item["created_at"] = datetime.utcnow().isoformat()
        item["updated_at"] = datetime.utcnow().isoformat()
        return container.create_item(body=item)
    
    def read_item(self, container_name: str, item_id: str, partition_key: str) -> Optional[Dict[str, Any]]:
        container = self.get_container(container_name)
        try:
            return container.read_item(item=item_id, partition_key=partition_key)
        except CosmosResourceNotFoundError:
            return None
    
    def update_item(self, container_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
        container = self.get_container(container_name)
        item["updated_at"] = datetime.utcnow().isoformat()
        return container.replace_item(item=item["id"], body=item)
    
    def delete_item(self, container_name: str, item_id: str, partition_key: str):
        container = self.get_container(container_name)
        container.delete_item(item=item_id, partition_key=partition_key)
    
    def query_items(self, container_name: str, query: str, parameters: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        container = self.get_container(container_name)
        items = list(container.query_items(
            query=query,
            parameters=parameters or [],
            enable_cross_partition_query=True
        ))
        return items
    
    def get_user_items(self, container_name: str, user_id: str) -> List[Dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.user_id = @user_id ORDER BY c.created_at DESC"
        parameters = [{"name": "@user_id", "value": user_id}]
        return self.query_items(container_name, query, parameters)


# Global instance
cosmos_client = CosmosDBClient()