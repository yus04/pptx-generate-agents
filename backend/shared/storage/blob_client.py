from azure.storage.blob import BlobServiceClient, BlobClient
from azure.core.exceptions import ResourceNotFoundError
from typing import Optional, BinaryIO
import uuid
from datetime import datetime, timedelta

from ..config import settings


class BlobStorageClient:
    def __init__(self):
        self.client = BlobServiceClient.from_connection_string(
            settings.blob_storage_connection_string
        )
        self.container_name = settings.blob_container_name
        self._ensure_container()
    
    def _ensure_container(self):
        """コンテナーが存在しない場合は作成"""
        try:
            self.client.get_container_client(self.container_name)
        except ResourceNotFoundError:
            self.client.create_container(self.container_name)
    
    def upload_file(self, file_data: BinaryIO, file_name: str, user_id: str, file_type: str = "pptx") -> str:
        """ファイルをアップロードして URL を返す"""
        blob_name = f"{user_id}/{file_type}/{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid.uuid4()}_{file_name}"
        
        blob_client = self.client.get_blob_client(
            container=self.container_name,
            blob=blob_name
        )
        
        blob_client.upload_blob(file_data, overwrite=True)
        return blob_client.url
    
    def upload_bytes(self, data: bytes, file_name: str, user_id: str, file_type: str = "pptx") -> str:
        """バイトデータをアップロードして URL を返す"""
        blob_name = f"{user_id}/{file_type}/{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid.uuid4()}_{file_name}"
        
        blob_client = self.client.get_blob_client(
            container=self.container_name,
            blob=blob_name
        )
        
        blob_client.upload_blob(data, overwrite=True)
        return blob_client.url
    
    def download_file(self, blob_url: str) -> Optional[bytes]:
        """URL からファイルをダウンロード"""
        try:
            blob_name = blob_url.split(f"{self.container_name}/")[-1]
            blob_client = self.client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            return blob_client.download_blob().readall()
        except ResourceNotFoundError:
            return None
    
    def delete_file(self, blob_url: str) -> bool:
        """ファイルを削除"""
        try:
            blob_name = blob_url.split(f"{self.container_name}/")[-1]
            blob_client = self.client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            blob_client.delete_blob()
            return True
        except ResourceNotFoundError:
            return False
    
    def generate_sas_url(self, blob_url: str, expiry_hours: int = 24) -> str:
        """SAS URL を生成（期限付きアクセス）"""
        blob_name = blob_url.split(f"{self.container_name}/")[-1]
        blob_client = self.client.get_blob_client(
            container=self.container_name,
            blob=blob_name
        )
        
        from azure.storage.blob import generate_blob_sas, BlobSasPermissions
        
        sas_token = generate_blob_sas(
            account_name=blob_client.account_name,
            container_name=self.container_name,
            blob_name=blob_name,
            account_key=blob_client.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
        )
        
        return f"{blob_url}?{sas_token}"


# Global instance
blob_client = BlobStorageClient()