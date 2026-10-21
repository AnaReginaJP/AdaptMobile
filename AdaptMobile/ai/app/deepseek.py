"""
Cliente DeepSeek (API compatible con OpenAI: POST /chat/completions).

Reglas de diseño:
  * Si no hay API key, o la llamada falla (red, 401, timeout, JSON inválido),
    se devuelve None y el motor cae a la heurística determinista: el producto
    NUNCA se queda sin responder ni gasta de más.
  * La key se resuelve en CADA llamada a través del keyring, lo que permite
    rotarla en caliente sin reiniciar el contenedor.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from .config import settings
from .keyring import key_store

logger = logging.getLogger("deepseek")

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class DeepSeekClient:
    def __init__(self) -> None:
        self.last_error: Optional[str] = None

    # ------------------------------------------------------------------ estado
    @property
    def enabled(self) -> bool:
        """True si AI_PROVIDER=deepseek (haya o no key)."""
        return settings.provider == "deepseek"

    def available(self) -> bool:
        """True si además hay una key utilizable."""
        return self.enabled and key_store.configured()

    def status(self) -> Dict[str, Any]:
        """Estado publicable (nunca incluye la key completa)."""
        return {
            "provider": settings.provider,
            "model": settings.llm_model,
            "base_url": settings.deepseek_base_url,
            "mode": "deepseek" if self.available() else "heuristic",
            "key_configured": key_store.configured(),
            "key_source": key_store.source(),
            "key_masked": key_store.masked(),
            "last_error": self.last_error,
        }

    # ----------------------------------------------------------------- llamada
    def _complete(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        if not self.available():
            return None

        payload: Dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens or settings.deepseek_max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            with httpx.Client(timeout=settings.deepseek_timeout) as client:
                resp = client.post(
                    f"{settings.deepseek_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key_store.get()}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except Exception as exc:  # red caída, DNS, timeout...
            self.last_error = f"conexión: {exc}"
            logger.warning("DeepSeek inaccesible, se usa la heurística determinista: %s", exc)
            return None

        if resp.status_code >= 400:
            self.last_error = f"HTTP {resp.status_code}"
            logger.warning("DeepSeek respondió %s: %s", resp.status_code, resp.text[:300])
            return None

        try:
            data = resp.json()
        except Exception as exc:
            self.last_error = f"respuesta ilegible: {exc}"
            return None

        choices = data.get("choices") or []
        if not choices:
            self.last_error = "respuesta sin 'choices'"
            return None

        self.last_error = None
        return ((choices[0].get("message") or {}).get("content") or "").strip() or None

    def chat_json(self, system: str, user: str, max_tokens: Optional[int] = None) -> Optional[Dict[str, Any]]:
        raw = self._complete(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            json_mode=True,
            max_tokens=max_tokens,
        )
        if not raw:
            return None

        text = _FENCE.sub("", raw).strip()
        try:
            parsed = json.loads(text)
        except Exception:
            match = re.search(r"\{.*\}", text, re.S)
            if not match:
                self.last_error = "contenido no parseable como JSON"
                return None
            try:
                parsed = json.loads(match.group(0))
            except Exception:
                self.last_error = "contenido no parseable como JSON"
                return None
        return parsed if isinstance(parsed, dict) else None

    def chat_text(self, system: str, user: str, max_tokens: Optional[int] = None) -> Optional[str]:
        return self._complete(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            json_mode=False,
            max_tokens=max_tokens,
        )


deepseek = DeepSeekClient()
