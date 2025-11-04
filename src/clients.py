import httpx
from typing import Dict, Optional
from config import REQUEST_TIMEOUT


def _auth_headers(incoming_headers: Dict[str, str]) -> Dict[str, str]:
    auth = incoming_headers.get("Authorization")
    return {"Authorization": auth} if auth else {}


def post_json(url: str, payload: dict, headers: Dict[str, str]):
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        return client.post(url, json=payload, headers=headers)


def get_json(url: str, headers: Dict[str, str]):
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        return client.get(url, headers=headers)


def request_json(method: str, url: str, headers: Dict[str, str],
                 json: Optional[dict] = None, params: Optional[dict] = None):
    method_upper = (method or "GET").upper()
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        return client.request(method_upper, url, headers=headers, json=json, params=params)

