import os
from pydantic import BaseModel


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


class AISettings(BaseModel):
    provider: str = _env("AI_PROVIDER", "heuristic").lower()
    openai_api_key: str = _env("OPENAI_API_KEY")
    gemini_api_key: str = _env("GEMINI_API_KEY")
    model_name: str = _env("AI_MODEL_NAME")

    # ---------- DeepSeek ----------
    # La key puede venir de la variable de entorno o de un archivo (ver keyring.py).
    deepseek_api_key: str = _env("DEEPSEEK_API_KEY")
    deepseek_api_key_file: str = _env("DEEPSEEK_API_KEY_FILE")
    deepseek_base_url: str = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    deepseek_model: str = _env("DEEPSEEK_MODEL", "deepseek-chat")
    deepseek_timeout: float = float(_env("DEEPSEEK_TIMEOUT", "45") or 45)
    deepseek_max_tokens: int = int(_env("DEEPSEEK_MAX_TOKENS", "1200") or 1200)

    # Token que protege los endpoints de rotación de la key (/admin/api-key).
    admin_token: str = _env("AI_ADMIN_TOKEN")

    @property
    def llm_model(self) -> str:
        """AI_MODEL_NAME tiene prioridad si está definido; si no, DEEPSEEK_MODEL."""
        return self.model_name or self.deepseek_model


settings = AISettings()
