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
    def __init__(self, api_key: str = "", api_key_file: str = "", label: str = "principal",
                 env_var: str = "DEEPSEEK_API_KEY", parent: Optional["KeyStore"] = None,
                 inherit_parent: bool = False) -> None:
        self._lock = threading.Lock()
        self._override: Optional[str] = None
        self._label = label
        self._api_key_file = api_key_file
        self._env_var = env_var
        self._parent = parent
        self._inherit_parent = inherit_parent and parent is not None
        self._boot = clean_key(api_key)

    # ------------------------------------------------------------------ fuentes
    def _from_file(self) -> str:
        path = self._api_key_file
        if not path:
            return ""
        try:
            if not os.path.isfile(path):
                return ""
            with open(path, "r", encoding="utf-8") as fh:
                return clean_key(fh.read())
        except OSError as exc:
            logger.warning("No se pudo leer el archivo de key %s (%s): %s", self._label, path, exc)
            return ""

    def get(self) -> str:
        with self._lock:
            if self._override is not None:
                return self._override
        # Sin key propia configurada (DEEPSEEK_CHAT_API_KEY vacío): se hereda la del
        # principal, incluida la rotada en caliente desde el panel de administración.
        if self._inherit_parent and self._parent is not None:
            inherited = self._parent.get()
            if inherited:
                return inherited
        return self._from_file() or self._boot

    def source(self) -> str:
        with self._lock:
            if self._override is not None:
                return "memoria (rotada en caliente)"
        if self._inherit_parent and self._parent is not None and self._parent.configured():
            return f"{self._parent.source()} (heredada de la IA principal)"
        if self._from_file():
            return f"archivo {self._api_key_file}"
        if self._boot:
            return f"variable de entorno {self._env_var}"
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


key_store = KeyStore(
    settings.deepseek_api_key, settings.deepseek_api_key_file, "principal", "DEEPSEEK_API_KEY"
)

# Segunda IA (chat): si no tiene key propia, HEREDA la del principal, incluida la
# que se rota en caliente desde el panel de administración.
chat_key_store = KeyStore(
    settings.deepseek_chat_api_key,
    settings.deepseek_chat_api_key_file,
    "chat",
    "DEEPSEEK_CHAT_API_KEY",
    parent=key_store,
    inherit_parent=not bool(settings.deepseek_chat_api_key or settings.deepseek_chat_api_key_file),
)
