from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="user") # 'user' or 'admin'
    plan = Column(String(50), default="free") # 'free', 'pro', 'enterprise'
    credits_limit = Column(Integer, default=2) # 2 per month for free plan
    credits_used = Column(Integer, default=0)
    period_start = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Stripe (estructura lista; se rellena al activar los pagos reales)
    stripe_customer_id = Column(String(255), nullable=True, index=True)

    analyses = relationship("Analysis", back_populates="user", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="user", cascade="all, delete-orphan")

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    phone_brand = Column(String(100), index=True, nullable=False)
    phone_model = Column(String(255), index=True, nullable=False)
    ram_gb = Column(Float, index=True, nullable=True)
    storage_gb = Column(Float, nullable=True)
    os_type = Column(String(50), index=True, nullable=True) # iOS, Android, etc.
    os_version = Column(String(100), nullable=True)
    os_version_num = Column(Float, index=True, nullable=True)
    cpu = Column(Text, nullable=True)
    cpu_cores = Column(Integer, nullable=True)
    gpu = Column(Text, nullable=True)
    gpu_company = Column(String(100), nullable=True)
    chipset = Column(Text, nullable=True)
    display_resolution = Column(String(100), nullable=True)
    ppi_density = Column(Integer, nullable=True)
    battery_size = Column(String(50), nullable=True)
    price_usd = Column(Float, nullable=True)
    price_range = Column(String(50), nullable=True)
    release_year = Column(Integer, nullable=True)
    raw_specs = Column(JSON, nullable=True)
    # Mercado: MX / US / CA. region_basis = {"mx": "red", "us": "venta", ...}
    in_mx = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    in_us = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    in_ca = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    region_basis = Column(JSON, nullable=True)  # NULL = dato legado sin regionalizar
    # True = demasiado antiguo: solo se guarda para responder "No compatible"
    is_legacy = Column(Boolean, nullable=False, default=False, server_default="false", index=True)

    __table_args__ = (
        UniqueConstraint("phone_brand", "phone_model", "ram_gb", "storage_gb", name="uq_device_brand_model_ram_storage"),
    )

class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=True)
    project_name = Column(String(255), nullable=False)
    tech_stack = Column(JSON, nullable=True)
    requirements = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)
    recommendations = Column(JSON, nullable=True)
    region = Column(String(5), nullable=True, default="mx")  # mx | us | ca
    stats = Column(JSON, nullable=True) # { "total": 1708, "compatible": 1100, "limited": 400, "incompatible": 208 }
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="analyses")
    devices = relationship("AnalysisDevice", back_populates="analysis", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="analysis", cascade="all, delete-orphan")

class AnalysisDevice(Base):
    __tablename__ = "analysis_devices"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), nullable=False) # 'compatible', 'limited', 'incompatible'
    reason = Column(Text, nullable=False)

    analysis = relationship("Analysis", back_populates="devices")
    device = relationship("Device")

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_name = Column(String(255), nullable=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    analysis = relationship("Analysis", back_populates="questions")
    user = relationship("User", back_populates="questions")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    monthly_credits = Column(Integer, nullable=False)
    price_usd = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    features = Column(JSON, nullable=True)
    # Precio de Stripe asociado al plan (se rellena al activar los pagos reales)
    stripe_price_id = Column(String(255), nullable=True)


class UsageEvent(Base):
    """Un registro por cada crédito consumido (análisis o pregunta)."""
    __tablename__ = "usage_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(20), nullable=False, index=True)  # 'analysis' | 'question'
    analysis_id = Column(Integer, ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True, index=True)
    credits_spent = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class FunnelEvent(Base):
    """Evento del embudo de conversión (register, upload_started, ...)."""
    __tablename__ = "funnel_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event = Column(String(30), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class Payment(Base):
    """
    Estructura para pagos (todavía NO se cobra nada).
    Al activar Stripe: una fila por checkout.session.completed / invoice.paid.
    """
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True)
    provider = Column(String(30), nullable=False, default="stripe")
    provider_payment_id = Column(String(255), nullable=True, index=True)  # id de Stripe (pi_/cs_/in_)
    amount = Column(Float, nullable=True)
    currency = Column(String(3), nullable=False, default="usd")
    status = Column(String(30), nullable=False, default="pending")  # pending|succeeded|failed|refunded
    created_at = Column(DateTime, default=datetime.utcnow)
