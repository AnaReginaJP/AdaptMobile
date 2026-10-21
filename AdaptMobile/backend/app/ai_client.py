import httpx
import logging
from typing import Dict, Any, Optional
from .config import settings

logger = logging.getLogger("ai_client")

class AIClient:
    def __init__(self, base_url: str = settings.AI_SERVICE_URL):
        self.base_url = base_url.rstrip("/")

    async def estimate_requirements(self, filename: str, content: str) -> Dict[str, Any]:
        url = f"{self.base_url}/estimate-requirements"
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(url, json={"filename": filename, "content": content})
            resp.raise_for_status()
            return resp.json()

    async def generate_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/generate-report"
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def ask_question(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/ask-question"
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Rotación de la API key de DeepSeek: el microservicio ai la aplica en
    # caliente; el backend solo hace de proxy para el panel de administración.
    # ------------------------------------------------------------------
    def _admin_headers(self) -> Dict[str, str]:
        return {"X-Admin-Token": settings.AI_ADMIN_TOKEN}

    async def get_ai_key_status(self) -> Dict[str, Any]:
        url = f"{self.base_url}/admin/api-key"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self._admin_headers())
            resp.raise_for_status()
            return resp.json()

    async def set_ai_key(self, api_key: str) -> Dict[str, Any]:
        url = f"{self.base_url}/admin/api-key"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=self._admin_headers(), json={"api_key": api_key})
            resp.raise_for_status()
            return resp.json()

    async def clear_ai_key(self) -> Dict[str, Any]:
        url = f"{self.base_url}/admin/api-key"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(url, headers=self._admin_headers())
            resp.raise_for_status()
            return resp.json()

ai_client = AIClient()
