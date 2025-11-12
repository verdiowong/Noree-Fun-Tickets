import os
import time
from typing import Dict, Optional, Tuple
import httpx
import jwt
import json


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


class CognitoVerifier:
    def __init__(self, region: str, user_pool_id: str, app_client_id: str):
        self.region = region
        self.user_pool_id = user_pool_id
        self.app_client_id = app_client_id
        self.issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        self.jwks_url = f"{self.issuer}/.well-known/jwks.json"
        self._jwks_cache: Optional[Dict] = None
        self._jwks_loaded_at: float = 0.0
        self._jwks_ttl_seconds: int = 3600

    def _get_jwks(self) -> Dict:
        now = time.time()
        if self._jwks_cache and (now - self._jwks_loaded_at) < self._jwks_ttl_seconds:
            return self._jwks_cache
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(self.jwks_url)
            resp.raise_for_status()
            self._jwks_cache = resp.json()
            self._jwks_loaded_at = now
            return self._jwks_cache

    def verify_authorization_header(self, auth_header: Optional[str]) -> Tuple[Optional[dict], Optional[str]]:
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return None, "Missing or invalid Authorization header"
        token = auth_header.split(" ", 1)[1].strip()
        return self.verify_token(token)

    def verify_token(self, token: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            unverified = jwt.get_unverified_header(token)
            kid = unverified.get("kid")
            if not kid:
                return None, "Missing kid in token header"

            jwks = self._get_jwks()
            keys = jwks.get("keys", [])
            key = next((k for k in keys if k.get("kid") == kid), None)
            if not key:
                # refresh once in case of rotation
                self._jwks_cache = None
                jwks = self._get_jwks()
                keys = jwks.get("keys", [])
                key = next((k for k in keys if k.get("kid") == kid), None)
                if not key:
                    return None, f"Signing key not found for kid: {kid}"

            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
            
            claims = jwt.decode(
                token,
                key=public_key,
                algorithms=["RS256"],
                audience=self.app_client_id,
                issuer=self.issuer,
            )
            return claims, None
        except jwt.ExpiredSignatureError:
            return None, "Token has expired"
        except jwt.InvalidAudienceError:
            return None, "Invalid token audience"
        except jwt.InvalidIssuerError:
            return None, "Invalid token issuer"
        except jwt.DecodeError as e:
            return None, f"Token decode error: {str(e)}"
        except Exception as e:
            return None, f"Token validation failed: {str(e)}"


def build_verifier_from_env() -> Optional[CognitoVerifier]:
    region = _env("COGNITO_REGION")
    pool = _env("COGNITO_USER_POOL_ID")
    client_id = _env("COGNITO_APP_CLIENT_ID")
    if not (region and pool and client_id):
        return None
    return CognitoVerifier(region, pool, client_id)


