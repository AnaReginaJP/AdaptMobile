"""
Créditos, uso y embudo de conversión.

- `refresh_monthly_credits`: reinicio perezoso del contador al primer uso de un mes
  nuevo. No depende de cron: usa `users.period_start` como "último reinicio guardado".
- `log_usage_event`: una fila en `usage_events` por cada crédito consumido.
- `log_funnel_event` / `funnel_summary`: embudo de conversión (`funnel_events`).
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import FunnelEvent, UsageEvent, User

logger = logging.getLogger("telemetry")

CREDITS_EXHAUSTED_CODE = "credits_exhausted"

# Eventos aceptados en POST /api/events (el orden define los pasos del embudo)
FUNNEL_STEPS = (
    "register",
    "upload_started",
    "analysis_done",
    "limit_reached",
    "pricing_viewed",
    "upgrade_clicked",
)
FUNNEL_EVENTS = frozenset(FUNNEL_STEPS)


# --------------------------------------------------------------------------- créditos
def refresh_monthly_credits(db: Session, user: User) -> bool:
    """Pone credits_used en 0 si cambió el mes desde el último reinicio. True si reinició."""
    now = datetime.utcnow()
    last_reset = user.period_start or user.created_at or now
    if (now.year, now.month) == (last_reset.year, last_reset.month):
        return False

    logger.info("Reinicio mensual de créditos de %s (%s -> 0)", user.email, user.credits_used)
    user.credits_used = 0
    user.period_start = now
    db.commit()
    return True


def credits_available(db: Session, user: User) -> bool:
    """Los admin no consumen cuota; el resto solo si le quedan créditos del mes."""
    if user.role == "admin":
        return True
    refresh_monthly_credits(db, user)
    return user.credits_used < user.credits_limit


def credits_exhausted(user: User) -> HTTPException:
    """402 con código identificable: la web lo usa para abrir el modal de planes."""
    return HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "code": CREDITS_EXHAUSTED_CODE,
            "message": (
                f"Has agotado tus {user.credits_limit} análisis/preguntas de este mes. "
                "Mejora a Plan Pro o Enterprise para seguir analizando."
            ),
            "credits_used": user.credits_used,
            "credits_limit": user.credits_limit,
            "upgrade_action": "open_plans",
        },
    )


def log_usage_event(
    db: Session,
    user: User,
    action: str,
    analysis_id: Optional[int] = None,
    credits_spent: int = 1,
) -> UsageEvent:
    """Registra el consumo de un crédito. `action` es 'analysis' o 'question'."""
    event = UsageEvent(
        user_id=user.id,
        action=action,
        analysis_id=analysis_id,
        credits_spent=credits_spent,
    )
    db.add(event)
    db.commit()
    return event


# --------------------------------------------------------------------------- embudo
def log_funnel_event(db: Session, event: str, user_id: Optional[int] = None) -> Optional[FunnelEvent]:
    """Guarda un paso del embudo. Ignora eventos desconocidos (no rompe la petición)."""
    if event not in FUNNEL_EVENTS:
        logger.warning("Evento de embudo desconocido, ignorado: %r", event)
        return None
    row = FunnelEvent(user_id=user_id, event=event)
    db.add(row)
    db.commit()
    return row


def funnel_summary(db: Session) -> dict:
    """Conteos por evento + tasa de paso entre pasos consecutivos y desde 'register'."""
    raw = dict(db.query(FunnelEvent.event, func.count(FunnelEvent.id)).group_by(FunnelEvent.event).all())
    counts = {step: int(raw.get(step, 0)) for step in FUNNEL_STEPS}

    base = counts["register"]
    steps = []
    previous = None
    for step in FUNNEL_STEPS:
        count = counts[step]
        steps.append({
            "event": step,
            "count": count,
            "from_previous_pct": round(count / previous * 100, 1) if previous else None,
            "from_register_pct": round(count / base * 100, 1) if base else None,
        })
        previous = count
    return {"counts": counts, "steps": steps}
