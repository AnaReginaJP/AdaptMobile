import secrets as _secrets
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from .config import settings
from .engine import engine
from .keyring import chat_key_store, key_store
from .deepseek import chat_ai, deepseek

app = FastAPI(title="AdaptMobile AI Microservice", version="1.1.0")

class EstimateRequest(BaseModel):
    filename: str
    content: str

class ReportRequest(BaseModel):
    project_name: str
    detected_tech: Dict[str, Any]
    requirements: Dict[str, Any]
    stats: Dict[str, Any]
    region: Optional[str] = None
    sample_devices: Optional[List[Dict[str, Any]]] = None

class QuestionRequest(BaseModel):
    project_name: str
    requirements: Dict[str, Any]
    device_specs: Optional[Dict[str, Any]] = None
    question: str
    # Contexto extra para la segunda IA del chat (preguntas generales)
    region: Optional[str] = None
    summary: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    # Turnos previos de la conversación: [{"role": "user"|"assistant", "content": str}]
    history: Optional[List[Dict[str, str]]] = None

class ApiKeyIn(BaseModel):
    api_key: str

@app.get("/health")
def health():
    return {"status": "ok", "service": "adaptmobile-ai", **deepseek.status(), "chat": chat_ai.status()}

@app.post("/estimate-requirements")
def estimate_requirements(req: EstimateRequest):
    try:
        res = engine.estimate_requirements(req.filename, req.content)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error estimating requirements: {str(e)}")

@app.post("/generate-report")
def generate_report(req: ReportRequest):
    try:
        res = engine.generate_report(req.model_dump())
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

@app.post("/ask-question")
def ask_question(req: QuestionRequest):
    try:
        res = engine.ask_question(req.model_dump())
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error answering question: {str(e)}")


# ---------------------------------------------------------------------------
# Rotación de la API key de DeepSeek
# Protegido con el header X-Admin-Token == AI_ADMIN_TOKEN (.env).
# Si AI_ADMIN_TOKEN está vacío, los endpoints quedan deshabilitados (503) para
# que nadie pueda fijar una key en el servicio.
# ---------------------------------------------------------------------------
def _require_admin_token(x_admin_token: Optional[str]) -> None:
    expected = settings.admin_token
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Rotación de API key deshabilitada: define AI_ADMIN_TOKEN en el .env y recrea el contenedor.",
        )
    if not x_admin_token or not _secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Token de administración inválido.")


@app.get("/admin/api-key", tags=["admin"])
def get_api_key_status(x_admin_token: Optional[str] = Header(None)):
    """Estado de la IA principal y de la IA del chat: fuente, modo y versión enmascarada."""
    _require_admin_token(x_admin_token)
    return {**deepseek.status(), "chat": chat_ai.status()}


@app.post("/admin/api-key", tags=["admin"])
def rotate_api_key(payload: ApiKeyIn, x_admin_token: Optional[str] = Header(None)):
    """Rota la key en memoria: efecto inmediato en el motor y en el chat, sin reiniciar."""
    _require_admin_token(x_admin_token)
    try:
        key_store.set_override(payload.api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {**deepseek.status(), "chat": chat_ai.status()}


@app.delete("/admin/api-key", tags=["admin"])
def clear_api_key(x_admin_token: Optional[str] = Header(None)):
    """Descarta los overrides (principal y chat) y vuelve al archivo / variable de entorno."""
    _require_admin_token(x_admin_token)
    removed_main = key_store.clear_override()
    removed_chat = chat_key_store.clear_override()
    return {
        "override_removed": removed_main or removed_chat,
        "override_removed_main": removed_main,
        "override_removed_chat": removed_chat,
        **deepseek.status(),
        "chat": chat_ai.status(),
    }
