"""
Estado de la IA para la web (punto verde/rojo del chat).

  GET /api/ai/status -> ¿está operativa la IA del chat? ¿y el motor de análisis?

Nunca devuelve la API key: solo el modo, el modelo y la fuente (archivo/entorno/panel).
"""
import logging

from fastapi import APIRouter, Depends

from ..ai_client import ai_client
from ..auth import get_current_user
from ..models import User
from ..schemas import AIStatusOut

logger = logging.getLogger("ai_status")

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/status", response_model=AIStatusOut)
async def get_ai_status(current_user: User = Depends(get_current_user)):
    """Estado de la IA conversacional y del motor, sin secretos."""
    try:
        raw = await ai_client.health()
    except Exception as e:
        logger.warning("No se pudo consultar el estado del servicio de IA: %s", e)
        return AIStatusOut(
            active=False,
            engine_active=False,
            mode="offline",
            last_error="servicio de IA no disponible",
        )

    chat = raw.get("chat") or {}
    return AIStatusOut(
        active=chat.get("mode") == "deepseek",
        engine_active=raw.get("mode") == "deepseek",
        provider=raw.get("provider"),
        mode=chat.get("mode") or raw.get("mode"),
        model=raw.get("model"),
        chat_model=chat.get("model"),
        key_source=chat.get("key_source"),
        last_error=chat.get("last_error"),
    )
