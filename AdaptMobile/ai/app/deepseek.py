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
from .keyring import chat_key_store, key_store

logger = logging.getLogger("deepseek")

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class DeepSeekClient:
    """
    Cliente de un modelo DeepSeek. `store` y `model` permiten tener varias
    instancias (por ejemplo, una segunda IA solo para el chat).
    """

    def __init__(self, store=None, model: Optional[str] = None, label: str = "principal") -> None:
        self._store = store or key_store
        self._fixed_model = model
        self._label = label
        self.last_error: Optional[str] = None

    @property
    def model(self) -> str:
        return self._fixed_model or settings.llm_model

    # ------------------------------------------------------------------ estado
    @property
    def enabled(self) -> bool:
        """True si AI_PROVIDER=deepseek (haya o no key)."""
        return settings.provider == "deepseek"

    def available(self) -> bool:
        """True si además hay una key utilizable."""
        return self.enabled and self._store.configured()

    def status(self) -> Dict[str, Any]:
        """Estado publicable (nunca incluye la key completa)."""
        return {
            "provider": settings.provider,
            "model": self.model,
            "base_url": settings.deepseek_base_url,
            "mode": "deepseek" if self.available() else "heuristic",
            "key_configured": self._store.configured(),
            "key_source": self._store.source(),
            "key_masked": self._store.masked(),
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
            "model": self.model,
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
                        "Authorization": f"Bearer {self._store.get()}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except Exception as exc:  # red caída, DNS, timeout...
            self.last_error = f"conexión: {exc}"
            logger.warning("%s inaccesible, se usa la heurística determinista: %s", self._label, exc)
            return None

        if resp.status_code >= 400:
            self.last_error = f"HTTP {resp.status_code}"
            logger.warning("%s respondió %s: %s", self._label, resp.status_code, resp.text[:300])
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

    def chat_messages(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None) -> Optional[str]:
        """Conversación completa: system + turnos previos + pregunta actual."""
        return self._complete(messages, json_mode=False, max_tokens=max_tokens)

    def chat_text(self, system: str, user: str, max_tokens: Optional[int] = None) -> Optional[str]:
        return self.chat_messages(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
        )


deepseek = DeepSeekClient(label="principal")

# Segunda IA: la que responde en el chat (puede usar otro modelo y otra key).
chat_ai = DeepSeekClient(store=chat_key_store, model=settings.chat_model, label="chat")
