from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import Payment, User, Subscription
from ..schemas import CheckoutRequest, SubscriptionOut, UpgradeRequest, UserOut
from ..auth import get_current_user
from ..config import settings

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])
# Los webhooks de Stripe NO llevan el prefijo /api/subscriptions
webhook_router = APIRouter(prefix="/api/webhooks", tags=["payments"])

NOT_IMPLEMENTED = (
    "Pagos no implementados todavía. El esquema (payments, stripe_customer_id, "
    "stripe_price_id) y el flujo están listos, pero la integración con Stripe "
    "se activa más adelante."
)

@router.get("", response_model=List[SubscriptionOut])
def get_plans(db: Session = Depends(get_db)):
    """Returns available subscription plans."""
    return db.query(Subscription).order_by(Subscription.price_usd.asc()).all()

@router.post("/upgrade", response_model=UserOut)
def upgrade_plan(
    payload: UpgradeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Simulated plan upgrade. Updates user plan and credits limit.
    MVP ready for credit/token subscription tiers without real payment processor.
    """
    plan_name = payload.plan_name.lower().strip()
    sub = db.query(Subscription).filter(Subscription.name == plan_name).first()
    if not sub:
        raise HTTPException(status_code=400, detail="Plan de suscripción no válido.")

    current_user.plan = sub.name
    current_user.credits_limit = sub.monthly_credits
    # Optionally reset usage or grant extra credits
    current_user.credits_used = 0
    db.commit()
    db.refresh(current_user)

    return current_user


# ---------------------------------------------------------------------------
# STUBS DE STRIPE: responden 501 y NO cobran nada.
# ---------------------------------------------------------------------------
@router.post("/checkout", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def create_checkout_session(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    STUB de Stripe Checkout (no cobra nada todavía).

    Qué haría al activarse (requiere STRIPE_SECRET_KEY y `pip install stripe`):
      1. Buscar el plan y su `subscriptions.stripe_price_id` (hoy es NULL).
      2. Asegurar el cliente en Stripe: si `users.stripe_customer_id` es NULL,
         stripe.Customer.create(email=current_user.email, metadata={"user_id": ...})
         y guardar el id devuelto.
      3. stripe.checkout.Session.create(
             mode="subscription",
             customer=current_user.stripe_customer_id,
             line_items=[{"price": sub.stripe_price_id, "quantity": 1}],
             success_url=f"{settings.FRONTEND_URL}/?checkout=ok",
             cancel_url=f"{settings.FRONTEND_URL}/?checkout=cancel",
             metadata={"user_id": current_user.id, "subscription_id": sub.id},
         )
      4. Devolver {"checkout_url": session.url} para que la web redirija.
    El plan NO se cambia aquí: se cambia cuando llega el webhook confirmado.
    """
    plan_name = (payload.plan_name or "").lower().strip()
    sub = db.query(Subscription).filter(Subscription.name == plan_name).first()
    if not sub:
        raise HTTPException(status_code=400, detail="Plan de suscripción no válido.")

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "code": "payments_not_implemented",
            "message": NOT_IMPLEMENTED,
            "plan": sub.name,
            "stripe_price_id": sub.stripe_price_id,  # NULL hasta configurar Stripe
            "next_steps": "Definir STRIPE_SECRET_KEY, rellenar subscriptions.stripe_price_id e implementar el paso 3.",
        },
    )


@webhook_router.post("/stripe", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def stripe_webhook(request: Request):
    """
    STUB del webhook de Stripe (no procesa nada todavía).

    Qué haría al activarse:
      1. Verificar la firma:
         stripe.Webhook.construct_event(await request.body(),
                                        request.headers["stripe-signature"],
                                        settings.STRIPE_WEBHOOK_SECRET)
      2. checkout.session.completed -> crear/actualizar `payments`
         (provider="stripe", provider_payment_id=session.id, amount, currency,
          status="succeeded") y activar plan + credits_limit del usuario.
      3. invoice.paid -> extender el periodo y reiniciar credits_used del usuario.
      4. customer.subscription.deleted -> volver al plan 'free'.
    Siempre debe responder 200 rápido: Stripe reintenta si no lo hace.
    """
    return {
        "code": "payments_not_implemented",
        "message": NOT_IMPLEMENTED,
        "received_headers": sorted(request.headers.keys()),
        "payments_table": Payment.__tablename__,
        "webhook_secret_configured": bool(settings.STRIPE_WEBHOOK_SECRET),
    }
