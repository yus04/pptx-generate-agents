from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.core.exceptions import ClientAuthenticationError
from typing import Optional, Dict, Any
import jwt
from datetime import datetime, timedelta

from ..config import settings


class AuthManager:
    def __init__(self):
        self.credential = ClientSecretCredential(
            tenant_id=settings.azure_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret
        )
    
    def verify_azure_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Entra ID トークンを検証"""
        try:
            # In a real implementation, you would validate against Entra ID
            # For now, we'll decode without verification for development
            decoded = jwt.decode(token, options={"verify_signature": False})
            return {
                "user_id": decoded.get("oid") or decoded.get("sub"),
                "email": decoded.get("email") or decoded.get("upn"),
                "name": decoded.get("name"),
                "tenant_id": decoded.get("tid")
            }
        except jwt.InvalidTokenError:
            return None
    
    def create_api_token(self, user_id: str, expires_hours: int = 24) -> str:
        """API アクセス用のトークンを生成"""
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(hours=expires_hours),
            "iat": datetime.utcnow(),
            "type": "api_access"
        }
        return jwt.encode(payload, settings.a2a_token_secret, algorithm="HS256")
    
    def verify_api_token(self, token: str) -> Optional[Dict[str, Any]]:
        """API トークンを検証"""
        try:
            payload = jwt.decode(token, settings.a2a_token_secret, algorithms=["HS256"])
            if payload.get("type") != "api_access":
                return None
            return payload
        except jwt.InvalidTokenError:
            return None
    
    def extract_user_from_token(self, authorization: str) -> Optional[str]:
        """Authorization ヘッダーからユーザーIDを抽出"""
        if not authorization or not authorization.startswith("Bearer "):
            return None
        
        token = authorization.replace("Bearer ", "")
        
        # Try Entra ID token first
        user_info = self.verify_azure_token(token)
        if user_info:
            return user_info["user_id"]
        
        # Try API token
        token_info = self.verify_api_token(token)
        if token_info:
            return token_info["user_id"]
        
        return None


# Global instance
auth_manager = AuthManager()