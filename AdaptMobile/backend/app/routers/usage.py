"""
Endpoints de uso y embudo (registro de eventos de la web).

  GET  /api/usage   -> historial de créditos consumidos del usuario autenticado
  POST /api/events  -> registra un paso del embudo (register, upload_started, ...)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import UsageEvent, User
from ..schemas import FunnelEventIn, UsageSummaryOut
from ..telemetry import FUNNEL_STEPS, log_funnel_event, refresh_monthly_credits

router = APIRouter(tags=["usage"])


@router.get("/api/usage", response_model=UsageSummaryOut)
def get_my_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
):
    """Historial de consumo de créditos del usuario y resumen del periodo actual."""
    refresh_monthly_credits(db, current_user)  # aplica el reinicio mensual si toca

    period_start = current_user.period_start or current_user.created_at
    events = (
        db.query(UsageEvent)
        .filter(UsageEvent.user_id == current_user.id)
        .order_by(desc(UsageEvent.created_at))
        .limit(limit)
        .all()
    )
    by_action = dict(
        db.query(UsageEvent.action, func.count(UsageEvent.id))
        .filter(UsageEvent.user_id == current_user.id)
        .group_by(UsageEvent.action)
        .all()
    )
    spent = (
        db.query(func.coalesce(func.sum(UsageEvent.credits_spent), 0))
        .filter(UsageEvent.user_id == current_user.id, UsageEvent.created_at >= period_start)
        .scalar()
        or 0
    )

    return {
        "events": events,
        "by_action": {k: int(v) for k, v in by_action.items()},
        "credits_used": current_user.credits_used,
        "credits_limit": current_user.credits_limit,
        "period_start": period_start,
        "credits_spent_this_period": int(spent),
    }


@router.post("/api/events", status_code=status.HTTP_201_CREATED)
def track_event(
    payload: FunnelEventIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Registra un evento del embudo desde la web.
    El evento 'limit_reached' también se registra en el backend al devolver el 402,
    así que la web solo lo manda cuando lo detecta antes de llamar a la API.
    """
    if payload.event not in FUNNEL_STEPS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Evento no válido: {payload.event!r}. Usa uno de: {list(FUNNEL_STEPS)}",
        )
    log_funnel_event(db, payload.event, user_id=current_user.id)
    return {"ok": True, "event": payload.event}
