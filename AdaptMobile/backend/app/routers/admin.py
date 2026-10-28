from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List
import httpx

from ..database import get_db
from ..models import User, Device, Analysis, Question, Subscription, UsageEvent
from ..schemas import (
    UserOut, UserUpdatePlan, AdminStatsOut, AIKeyUpdate, AIKeyStatus,
    AdminUsageOut, AdminFunnelOut,
)
from ..auth import get_current_admin
from ..ai_client import ai_client
from ..telemetry import funnel_summary

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/stats", response_model=AdminStatsOut)
def get_admin_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    total_users = db.query(User).count()
    total_analyses = db.query(Analysis).count()
    total_devices = db.query(Device).filter(Device.is_legacy.is_(False)).count()
    total_questions = db.query(Question).count()

    free_users = db.query(User).filter(User.plan == "free").count()
    pro_users = db.query(User).filter(User.plan == "pro").count()
    enterprise_users = db.query(User).filter(User.plan == "enterprise").count()

    return {
        "total_users": total_users,
        "total_analyses": total_analyses,
        "total_devices": total_devices,
        "total_questions": total_questions,
        "free_users": free_users,
        "pro_users": pro_users,
        "enterprise_users": enterprise_users
    }

@router.get("/users", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    return db.query(User).order_by(User.created_at.desc()).all()

@router.put("/users/{user_id}", response_model=UserOut)
def update_user_plan(
    user_id: int,
    payload: UserUpdatePlan,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if payload.plan:
        user.plan = payload.plan
    if payload.credits_limit is not None:
        user.credits_limit = payload.credits_limit
    if payload.credits_used is not None:
        user.credits_used = payload.credits_used
    if payload.role:
        user.role = payload.role

    db.commit()
    db.refresh(user)
    return user

@router.post("/users/{user_id}/reset-credits", response_model=UserOut)
def reset_user_credits(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    user.credits_used = 0
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# API key de DeepSeek: consultar, rotar y revertir (solo administradores).
# El microservicio ai la aplica al instante; aquí solo se hace de proxy.
# ---------------------------------------------------------------------------
def _ai_key_error(exc: Exception) -> HTTPException:
    if isinstance(exc, httpx.HTTPStatusError):
        detail = "AI_ADMIN_TOKEN inválido o rotación deshabilitada en el servicio de IA."
        if exc.response.status_code == 503:
            detail = "Define AI_ADMIN_TOKEN en el .env y recrea los contenedores para habilitar la rotación."
        elif exc.response.status_code == 400:
            detail = "La API key enviada no es válida."
        return HTTPException(status_code=exc.response.status_code, detail=detail)
    return HTTPException(status_code=502, detail=f"No se pudo contactar el servicio de IA: {exc}")


@router.get("/ai-key", response_model=AIKeyStatus)
async def get_ai_key_status(admin: User = Depends(get_current_admin)):
    """Muestra de qué fuente sale la key de DeepSeek y el modo efectivo (nunca la key completa)."""
    try:
        return await ai_client.get_ai_key_status()
    except Exception as e:
        raise _ai_key_error(e)


@router.put("/ai-key", response_model=AIKeyStatus)
async def rotate_ai_key(payload: AIKeyUpdate, admin: User = Depends(get_current_admin)):
    """Rota la API key en caliente: surte efecto en la siguiente llamada, sin reiniciar."""
    try:
        await ai_client.set_ai_key(payload.api_key)
        return await ai_client.get_ai_key_status()
    except Exception as e:
        raise _ai_key_error(e)


@router.delete("/ai-key", response_model=AIKeyStatus)
async def revert_ai_key(admin: User = Depends(get_current_admin)):
    """Descarta el override en memoria (motor y chat) y vuelve al archivo / .env."""
    try:
        # El propio DELETE devuelve el estado posterior + override_removed
        return await ai_client.clear_ai_key()
    except Exception as e:
        raise _ai_key_error(e)


# ---------------------------------------------------------------------------
# Uso de créditos y embudo de conversión
# ---------------------------------------------------------------------------
@router.get("/usage", response_model=AdminUsageOut)
def get_total_usage(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Uso total del sistema: eventos, créditos consumidos y usuarios que más consumen."""
    by_action = dict(
        db.query(UsageEvent.action, func.count(UsageEvent.id)).group_by(UsageEvent.action).all()
    )
    total_spent = int(
        db.query(func.coalesce(func.sum(UsageEvent.credits_spent), 0)).scalar() or 0
    )
    top_rows = (
        db.query(
            User.email,
            func.count(UsageEvent.id).label("events"),
            func.coalesce(func.sum(UsageEvent.credits_spent), 0).label("credits"),
        )
        .join(UsageEvent, UsageEvent.user_id == User.id)
        .group_by(User.email)
        .order_by(desc("events"))
        .limit(10)
        .all()
    )

    return {
        "total_events": db.query(UsageEvent).count(),
        "total_credits_spent": total_spent,
        "by_action": {k: int(v) for k, v in by_action.items()},
        "top_users": [
            {"email": email, "events": int(events), "credits": int(credits or 0)}
            for email, events, credits in top_rows
        ],
    }


@router.get("/funnel", response_model=AdminFunnelOut)
def get_funnel(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Conteos por evento del embudo y tasa de paso entre pasos."""
    return funnel_summary(db)
