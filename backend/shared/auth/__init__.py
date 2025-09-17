from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.core.exceptions import ClientAuthenticationError
from typing import Optional, Dict, Any
import jwt
from jwt import PyJWKClient
from datetime import datetime, timedelta

from ..config import settings


class AuthManager:
    def __init__(self, jwks_url: str = None):
        self.jwks_client = None
        self.audience = '00000003-0000-0000-c000-000000000000'
        self.issuer = f"https://sts.windows.net/{settings.azure_tenant_id}/"

        # Always initialize JWKS client for production-like authentication
        if settings.azure_tenant_id and settings.azure_client_id:
            try:
                jwks_url = jwks_url or f"https://login.microsoftonline.com/{settings.azure_tenant_id}/discovery/v2.0/keys"
                self.jwks_client = PyJWKClient(jwks_url)
                print(f"JWKS client initialized for tenant: {settings.azure_tenant_id}")
                print(f"Expected audience: {self.audience}")
                print(f"Expected issuer: {self.issuer}")
                print(f"JWKS URL: {jwks_url}")
            except Exception as e:
                print(f"Failed to initialize JWKS client: {e}")
                raise ValueError("JWKS client initialization required for authentication")
    
    def verify_azure_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Entra ID トークンを検証"""
        try:
            # In a real implementation, you would validate against Entra ID
            # For now, we'll decode without verification for development
            if not self.jwks_client:
                raise ValueError("JWKS client not configured - authentication required")
                   
            # Get the unverified header to check the token
            unverified_header = jwt.get_unverified_header(token)
            print(f"Token header: {unverified_header}")

            # Get the signing key
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            # デバッグ用：トークンの内容を確認（署名検証なし）
            try:
                unverified_payload = jwt.decode(token, options={"verify_signature": False})
                print(f"Unverified payload: {unverified_payload}")
                print(f"Expected audience: {self.audience}")
                print(f"Token audience: {unverified_payload.get('aud')}")
                print(f"Token issuer: {unverified_payload.get('iss')}")

                # Check if this is a Microsoft Graph token instead of our app token
                token_audience = unverified_payload.get('aud')
                if token_audience == '00000003-0000-0000-c000-000000000000':
                    print("Token is for Microsoft Graph - extracting user info without full validation")
                    # For Graph tokens, extract user info directly (development mode)
                    return self._extract_user_info_from_payload(unverified_payload)
            except Exception as decode_error:
                print(f"Failed to decode token for debugging: {decode_error}")

            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True
                }
            )

            print(f"Token payload validated: {payload}")
            # return payload
            return self._extract_user_info_from_payload(payload)
        except jwt.ExpiredSignatureError:
            print("Token has expired")
            return None
        except jwt.InvalidAudienceError:
            print("Invalid audience")
            return None
        except jwt.InvalidIssuerError:
            print("Invalid issuer")
            return None
        except Exception as e:
            print(f"Unexpected error during token validation: {e}")
            print(f"Token type: {type(token)}")
            # Return anonymous user for development

            # デバッグ用：トークンの内容を確認（署名検証なし）
            try:
                unverified_payload = jwt.decode(token, options={"verify_signature": False})
                print(f"Unverified payload: {unverified_payload}")
                print(f"Expected audience: {self.audience}")
                print(f"Token audience: {unverified_payload.get('aud')}")
                print(f"Expected issuer: {self.issuer}")
                print(f"Token issuer: {unverified_payload.get('iss')}")
            except Exception as decode_error:
                print(f"Failed to decode token for debugging: {decode_error}")
            return None
    
    
    def _extract_user_info_from_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """トークンペイロードから標準化されたユーザー情報を抽出"""
        return {
            'sub': payload.get('oid') or payload.get('sub'),
            'user_id': payload.get('oid') or payload.get('sub'),
            'name': payload.get('name'),
            'upn': payload.get('upn'),
            'email': payload.get('upn') or payload.get('email'),
            'tenant_id': payload.get('tid'),
            'preferred_username': payload.get('preferred_username'),
            'unique_name': payload.get('unique_name'),
            'aud': payload.get('aud'),
            'iss': payload.get('iss'),
            'exp': payload.get('exp'),
            'iat': payload.get('iat'),
            'app_id': payload.get('appid')
        }
    
    
    def extract_user_from_token(self, authorization: str) -> Optional[Dict[str, Any]]:
        """Authorization ヘッダーからユーザー情報を抽出"""
        if not authorization or not authorization.startswith("Bearer "):
            return None
        
        token = authorization.replace("Bearer ", "")
        
        # Try Entra ID token first
        user_info = self.verify_azure_token(token)
        if user_info:
            return user_info
        
        
        return None


# Global instance
auth_manager = AuthManager()