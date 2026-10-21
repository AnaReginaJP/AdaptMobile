from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Auth & User ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    plan: str
    credits_limit: int
    credits_used: int
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

class UserUpdatePlan(BaseModel):
    plan: str
    credits_limit: Optional[int] = None
    credits_used: Optional[int] = None
    role: Optional[str] = None

# --- Device ---
class DeviceOut(BaseModel):
    id: int
    phone_brand: str
    phone_model: str
    ram_gb: Optional[float] = None
    storage_gb: Optional[float] = None
    os_type: Optional[str] = None
    os_version: Optional[str] = None
    cpu: Optional[str] = None
    gpu: Optional[str] = None
    chipset: Optional[str] = None
    display_resolution: Optional[str] = None
    ppi_density: Optional[int] = None
    battery_size: Optional[str] = None
    price_usd: Optional[float] = None
    price_range: Optional[str] = None
    release_year: Optional[int] = None
    in_mx: bool = False
    in_us: bool = False
    in_ca: bool = False

    class Config:
        from_attributes = True

class AnalysisDeviceOut(BaseModel):
    id: int
    device_id: int
    status: str
    reason: str
    device: DeviceOut

    class Config:
        from_attributes = True

# --- Analysis ---
class AnalysisSummaryOut(BaseModel):
    id: int
    filename: str
    file_type: Optional[str] = None
    project_name: str
    region: Optional[str] = None
    created_at: datetime
    stats: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class AnalysisDetailOut(BaseModel):
    id: int
    filename: str
    file_type: Optional[str] = None
    project_name: str
    region: Optional[str] = None
    tech_stack: Optional[Dict[str, Any]] = None
    requirements: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    stats: Optional[Dict[str, Any]] = None
    created_at: datetime
    devices: Optional[List[AnalysisDeviceOut]] = None

    class Config:
        from_attributes = True

# --- Question / Chat ---
class QuestionCreate(BaseModel):
    analysis_id: int
    question: str
    device_name: Optional[str] = None

class QuestionOut(BaseModel):
    id: int
    analysis_id: int
    question: str
    answer: str
    device_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# --- Subscriptions ---
class SubscriptionOut(BaseModel):
    id: int
    name: str
    monthly_credits: int
    price_usd: float
    description: Optional[str] = None
    features: Optional[List[str]] = None

    class Config:
        from_attributes = True

class UpgradeRequest(BaseModel):
    plan_name: str # 'pro' or 'enterprise' or 'free'

# --- Admin Telemetry ---
class AdminStatsOut(BaseModel):
    total_users: int
    total_analyses: int
    total_devices: int
    total_questions: int
    free_users: int
    pro_users: int
    enterprise_users: int

# --- Rotación de la API key de DeepSeek (solo admin) ---
class AIKeyUpdate(BaseModel):
    api_key: str

class AIKeyStatus(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    mode: Optional[str] = None
    key_configured: Optional[bool] = None
    key_source: Optional[str] = None
    key_masked: Optional[str] = None
    last_error: Optional[str] = None

# --- Uso de créditos ---
class UsageEventOut(BaseModel):
    id: int
    action: str
    analysis_id: Optional[int] = None
    credits_spent: int
    created_at: datetime

    class Config:
        from_attributes = True

class UsageSummaryOut(BaseModel):
    events: List[UsageEventOut]
    by_action: Dict[str, int] = {}
    credits_used: int
    credits_limit: int
    period_start: Optional[datetime] = None
    credits_spent_this_period: int = 0

class AdminUsageOut(BaseModel):
    total_events: int
    total_credits_spent: int
    by_action: Dict[str, int] = {}
    top_users: List[Dict[str, Any]] = []

# --- Embudo de conversión ---
class FunnelEventIn(BaseModel):
    event: str

class FunnelStepOut(BaseModel):
    event: str
    count: int
    from_previous_pct: Optional[float] = None
    from_register_pct: Optional[float] = None

class AdminFunnelOut(BaseModel):
    counts: Dict[str, int] = {}
    steps: List[FunnelStepOut] = []

# --- Pagos (solo estructura, sin cobrar) ---
class CheckoutRequest(BaseModel):
    plan_name: str
