from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional

from ..database import get_db
from ..models import Device
from ..schemas import DeviceOut
from ..regions import normalize_region, region_attr

router = APIRouter(prefix="/api/devices", tags=["devices"])

def _region_or_400(region: str) -> str:
    try:
        return normalize_region(region)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("", response_model=List[DeviceOut])
def get_devices(
    db: Session = Depends(get_db),
    brand: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    os_type: Optional[str] = Query(None),
    region: str = Query("mx", description="mx | us | ca"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=100)
):
    """Browses the verified phone database."""
    region = _region_or_400(region)
    q = db.query(Device).filter(getattr(Device, region_attr(region)).is_(True))
    if brand:
        q = q.filter(Device.phone_brand.ilike(f"%{brand}%"))
    if os_type:
        q = q.filter(Device.os_type.ilike(f"%{os_type}%"))
    if search:
        s = f"%{search}%"
        q = q.filter(or_(Device.phone_model.ilike(s), Device.phone_brand.ilike(s), Device.chipset.ilike(s)))

    devices = q.order_by(Device.phone_brand.asc(), Device.phone_model.asc()).offset(skip).limit(limit).all()
    return devices

@router.get("/brands")
def get_brands(db: Session = Depends(get_db), region: str = Query("mx")):
    """Returns unique brands available in the selected region."""
    region = _region_or_400(region)
    brands = db.query(Device.phone_brand).filter(getattr(Device, region_attr(region)).is_(True)).distinct().order_by(Device.phone_brand.asc()).all()
    return [b[0].capitalize() for b in brands if b[0]]

@router.get("/count")
def get_device_count(db: Session = Depends(get_db)):
    return {
        "total_devices": db.query(Device).filter(Device.is_legacy.is_(False)).count(),
        "mx": db.query(Device).filter(Device.in_mx.is_(True)).count(),
        "us": db.query(Device).filter(Device.in_us.is_(True)).count(),
        "ca": db.query(Device).filter(Device.in_ca.is_(True)).count(),
    }

@router.get("/{device_id}", response_model=DeviceOut)
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado en la base de datos.")
    return device
