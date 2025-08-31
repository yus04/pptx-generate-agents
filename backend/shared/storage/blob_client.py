from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from typing import Optional, BinaryIO
import uuid
import logging
import json
import base64
from datetime import datetime

from shared.config import settings

# ログ設定
logger = logging.getLogger(__name__)

class BlobStorageClient:
    def __init__(self):
        # 詳細ログ設定をする場合は以下のコメントを外す
        # logging.basicConfig(level=logging.INFO)
        
        credential = DefaultAzureCredential()
        account_name = settings.blob_storage_account_name
        account_url = f"https://{account_name}.blob.core.windows.net"

        # 使用しているプリンシパル情報をログ出力
        logger.info(f"=== Azure Blob Storage Client Initialization ===")
        logger.info(f"Storage Account: {account_name}")
        logger.info(f"Account URL: {account_url}")
        logger.info(f"Container Name: {settings.blob_container_name}")
        
        # 認証情報の詳細を出力
        try:
            # DefaultAzureCredentialの内部情報を取得
            logger.info(f"Credential type: {type(credential).__name__}")
            if hasattr(credential, '_sources'):
                logger.info(f"Available credential sources:")
                for i, source in enumerate(credential._sources):
                    logger.info(f"  {i+1}. {type(source).__name__}")
            
            # プリンシパル情報を取得 (同期的に)
            try:
                token = credential.get_token("https://storage.azure.com/.default")
                logger.info(f"Token acquired: expires at {datetime.fromtimestamp(token.expires_on)}")
                
                # トークンをデコードしてプリンシパル情報を取得
                try:
                    # JWTトークンの場合、payloadをデコード
                    token_parts = token.token.split('.')
                    if len(token_parts) >= 2:
                        # Base64デコード（パディング追加）
                        payload = token_parts[1]
                        payload += '=' * (4 - len(payload) % 4)  # パディング追加
                        decoded_payload = base64.b64decode(payload)
                        token_claims = json.loads(decoded_payload.decode('utf-8'))
                        
                        logger.info("=== Token Claims ===")
                        logger.info(f"Application ID (appid): {token_claims.get('appid', 'N/A')}")
                        logger.info(f"Object ID (oid): {token_claims.get('oid', 'N/A')}")
                        logger.info(f"Principal name (upn): {token_claims.get('upn', 'N/A')}")
                        logger.info(f"Tenant ID (tid): {token_claims.get('tid', 'N/A')}")
                        logger.info(f"Identity provider (idp): {token_claims.get('idp', 'N/A')}")
                        logger.info(f"App display name: {token_claims.get('app_displayname', 'N/A')}")
                        logger.info(f"Authentication method: {token_claims.get('amr', 'N/A')}")
                        
                except Exception as decode_error:
                    logger.warning(f"Could not decode token: {decode_error}")
                    
            except Exception as token_error:
                logger.error(f"Could not get token: {token_error}")
                    
        except Exception as e:
            logger.warning(f"Could not get credential details: {e}")

        # 環境変数の確認
        import os
        logger.info(f"=== Environment Variables ===")
        azure_env_vars = {
            'AZURE_TENANT_ID': os.getenv('AZURE_TENANT_ID', 'Not set'),
            'AZURE_CLIENT_ID': os.getenv('AZURE_CLIENT_ID', 'Not set'),
            'AZURE_CLIENT_SECRET': '***' if os.getenv('AZURE_CLIENT_SECRET') else 'Not set',
            'AZURE_SUBSCRIPTION_ID': os.getenv('AZURE_SUBSCRIPTION_ID', 'Not set'),
            'AZURE_RESOURCE_GROUP': os.getenv('AZURE_RESOURCE_GROUP', 'Not set'),
        }
        
        for key, value in azure_env_vars.items():
            logger.info(f"{key}: {value}")

        self.client = BlobServiceClient(
            account_url=account_url,
            credential=credential
        )
        self.container_name = settings.blob_container_name
        
        # 認証テスト
        try:
            logger.info("Testing authentication by listing containers...")
            containers = list(self.client.list_containers())
            logger.info(f"Successfully authenticated! Found {len(containers)} containers")
            for container in containers:
                logger.info(f"  - Container: {container['name']}")
        except Exception as auth_error:
            logger.error(f"Authentication failed: {auth_error}")
            logger.error(f"Error type: {type(auth_error).__name__}")
            raise
        
        self._ensure_container()
    
    def _ensure_container(self):
        """コンテナーが存在しない場合は作成"""
        try:
            logger.info(f"Checking if container '{self.container_name}' exists...")
            container_client = self.client.get_container_client(self.container_name)
            # コンテナーの存在確認
            container_client.get_container_properties()
            logger.info(f"Container '{self.container_name}' exists")
        except ResourceNotFoundError:
            logger.info(f"Container '{self.container_name}' does not exist, creating...")
            try:
                self.client.create_container(self.container_name)
                logger.info(f"Container '{self.container_name}' created successfully")
            except Exception as create_error:
                logger.error(f"Failed to create container '{self.container_name}': {create_error}")
                logger.error(f"Error type: {type(create_error).__name__}")
                raise
        except Exception as e:
            logger.error(f"Error checking container '{self.container_name}': {e}")
            logger.error(f"Error type: {type(e).__name__}")
            raise
    
    def upload_file(self, file_data: BinaryIO, file_name: str, user_id: str, file_type: str = "pptx") -> str:
        """ファイルをアップロードして URL を返す"""
        blob_name = f"{user_id}/{file_type}/{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid.uuid4()}_{file_name}"
        
        logger.info(f"=== Uploading file ===")
        logger.info(f"Blob name: {blob_name}")
        logger.info(f"Container: {self.container_name}")
        logger.info(f"User ID: {user_id}")
        logger.info(f"File type: {file_type}")
        
        try:
            blob_client = self.client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            logger.info(f"Blob client URL: {blob_client.url}")
            
            blob_client.upload_blob(file_data, overwrite=True)
            logger.info(f"File uploaded successfully: {blob_client.url}")
            return blob_client.url
        except Exception as upload_error:
            logger.error(f"Upload failed: {upload_error}")
            logger.error(f"Error type: {type(upload_error).__name__}")
            raise
    
    def upload_bytes(self, data: bytes, file_name: str, user_id: str, file_type: str = "pptx") -> str:
        """バイトデータをアップロードして URL を返す"""
        blob_name = f"{user_id}/{file_type}/{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid.uuid4()}_{file_name}"
        
        logger.info(f"=== Uploading bytes data ===")
        logger.info(f"Blob name: {blob_name}")
        logger.info(f"Container: {self.container_name}")
        logger.info(f"User ID: {user_id}")
        logger.info(f"File type: {file_type}")
        logger.info(f"Data size: {len(data)} bytes")
        
        try:
            blob_client = self.client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            logger.info(f"Blob client URL: {blob_client.url}")
            
            blob_client.upload_blob(data, overwrite=True)
            logger.info(f"Bytes uploaded successfully: {blob_client.url}")
            return blob_client.url
        except Exception as upload_error:
            logger.error(f"Upload failed: {upload_error}")
            logger.error(f"Error type: {type(upload_error).__name__}")
            raise
    
    def upload_file_from_bytes(self, data: bytes, blob_url: str) -> bool:
        """指定されたURLに直接バイトデータをアップロード（上書き）"""
        try:
            # URLからblob名を抽出
            blob_name = blob_url.split(f"{self.container_name}/")[-1]
            
            logger.info(f"=== Uploading bytes to existing blob ===")
            logger.info(f"Blob name: {blob_name}")
            logger.info(f"Container: {self.container_name}")
            logger.info(f"Data size: {len(data)} bytes")
            logger.info(f"Target URL: {blob_url}")
            
            blob_client = self.client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            blob_client.upload_blob(data, overwrite=True)
            logger.info(f"File successfully overwritten at: {blob_url}")
            return True
            
        except Exception as upload_error:
            logger.error(f"Failed to upload to existing blob: {upload_error}")
            logger.error(f"Error type: {type(upload_error).__name__}")
            return False
    
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

# Global instance
blob_client = BlobStorageClient()
