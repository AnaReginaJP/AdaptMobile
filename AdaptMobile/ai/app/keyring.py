"""
Resolución de la API key de DeepSeek con rotación en caliente (sin reiniciar contenedores).

Precedencia:
  1. Override en memoria -> POST /admin/api-key  (efecto inmediato, se pierde al reiniciar).
  2. Archivo             -> DEEPSEEK_API_KEY_FILE, se RELEE en cada petición: editas
                            secrets/deepseek_api_key en el host y la nueva key ya está activa.
  3. Variable de entorno -> DEEPSEEK_API_KEY (se aplica al recrear el contenedor: docker compose up -d ai).

Motivo: rotar la key seguido por seguridad sin rebuild ni downtime.
La key nunca se escribe en logs ni en respuestas: solo se expone enmascarada.
"""
import logging
import os
import threading
from typing import Optional

from .config import settings

logger = logging.getLogger("ai_keyring")

# Valores que la gente deja en los .env y que NO son una key real
_PLACEHOLDERS = {"changeme", "tu_api_key", "your_api_key", "none", "null", "undefined", "xxx"}


def clean_key(raw: Optional[str]) -> str:
    """Toma la primera línea útil: ignora comentarios, comillas y espacios."""
    if not raw:
        return ""
    for line in str(raw).splitlines():
        line = line.strip().strip('"').strip("'").strip()
        if not line or line.startswith("#"):
            continue
        if line.lower() in _PLACEHOLDERS:
            return ""
        return line
    return ""


class KeyStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._override: Optional[str] = None
        self._boot = clean_key(settings.deepseek_api_key)

    # ------------------------------------------------------------------ fuentes
    def _from_file(self) -> str:
        path = settings.deepseek_api_key_file
        if not path:
            return ""
        try:
            if not os.path.isfile(path):
                return ""
            with open(path, "r", encoding="utf-8") as fh:
                return clean_key(fh.read())
        except OSError as exc:
            logger.warning("No se pudo leer DEEPSEEK_API_KEY_FILE (%s): %s", path, exc)
            return ""

    def get(self) -> str:
        with self._lock:
            if self._override is not None:
                return self._override
        return self._from_file() or self._boot

    def source(self) -> str:
        with self._lock:
            if self._override is not None:
                return "memoria (rotada en caliente)"
        if self._from_file():
            return f"archivo {settings.deepseek_api_key_file}"
        if self._boot:
            return "variable de entorno DEEPSEEK_API_KEY"
        return "sin configurar"

    def configured(self) -> bool:
        return bool(self.get())

    # ---------------------------------------------------------------- rotación
    def set_override(self, api_key: str) -> str:
        """Rota la key en memoria. Devuelve la key enmascarada."""
        key = clean_key(api_key)
        if not key:
            raise ValueError("La API key está vacía o es un marcador de posición.")
        with self._lock:
            self._override = key
        logger.info("API key de DeepSeek rotada en memoria (%s).", self.masked())
        return self.masked()

    def clear_override(self) -> bool:
        """Vuelve a la key del archivo / variable de entorno. True si había algo que limpiar."""
        with self._lock:
            had = self._override is not None
            self._override = None
        if had:
            logger.info("Override en memoria eliminado; se usa la fuente configurada.")
        return had

    def masked(self) -> str:
        key = self.get()
        if not key:
            return ""
        if len(key) <= 8:
            return "*" * len(key)
        return f"{key[:4]}…{key[-4:]}"


key_store = KeyStore()
