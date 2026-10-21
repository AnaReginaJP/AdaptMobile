import csv
import json
import logging
import os
import re
from typing import Optional, Set, Tuple
from sqlalchemy.orm import Session
from .models import Device, Subscription, User, AnalysisDevice
from .regions import classify_regions, is_active_status
from .auth import get_password_hash
from .config import settings

logger = logging.getLogger("importer")

def clean_float(val) -> Optional[float]:
    if val is None or val == "" or str(val).strip() in ["-", "N/A", "null"]:
        return None
    try:
        return float(val)
    except Exception:
        m = re.search(r"(\d+(?:\.\d+)?)", str(val))
        return float(m.group(1)) if m else None

def clean_int(val) -> Optional[int]:
    if val is None or val == "" or str(val).strip() in ["-", "N/A", "null"]:
        return None
    try:
        return int(float(val))
    except Exception:
        m = re.search(r"(\d+)", str(val))
        return int(m.group(1)) if m else None

def seed_subscriptions_and_admin(db: Session):
    """Seeds default subscription plans and initial administrator."""
    # 1. Subscriptions
    plans = [
        {
            "name": "free",
            "monthly_credits": 2,
            "price_usd": 0.0,
            "description": "Plan básico para desarrolladores individuales.",
            "features": [
                "2 análisis o consultas mensuales",
                "Matriz de compatibilidad completa",
                "Detección de cuello de botella de RAM/SO",
                "Recomendaciones básicas de optimización"
            ]
        },
        {
            "name": "pro",
            "monthly_credits": 50,
            "price_usd": 29.0,
            "description": "Para desarrolladores independientes y pequeños estudios.",
            "features": [
                "50 análisis o consultas mensuales",
                "Filtro avanzado por GPU y Vulkan",
                "Exportación de reportes ejecutivos",
                "Soporte prioritario y análisis de shaders"
            ]
        },
        {
            "name": "enterprise",
            "monthly_credits": 9999,
            "price_usd": 99.0,
            "description": "Para equipos móviles y empresas de publicación de apps.",
            "features": [
                "Consultas y análisis ilimitados",
                "Integración con pipelines CI/CD",
                "Auditoría personalizada de rendimiento",
                "Múltiples asientos y panel de gestión de equipo"
            ]
        }
    ]

    for p in plans:
        existing = db.query(Subscription).filter(Subscription.name == p["name"]).first()
        if not existing:
            sub = Subscription(**p)
            db.add(sub)
    db.commit()

    # 2. Administrator
    admin_user = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
    if not admin_user:
        logger.info(f"Creating default admin account: {settings.ADMIN_EMAIL}")
        admin = User(
            email=settings.ADMIN_EMAIL,
            hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
            full_name="AdaptMobile Admin",
            role="admin",
            plan="enterprise",
            credits_limit=9999,
            credits_used=0
        )
        db.add(admin)
        db.commit()

_YEAR_RE = re.compile(r"(?:19|20)\d{2}")


def _year_from(text_val) -> Optional[int]:
    m = _YEAR_RE.search(str(text_val or ""))
    return int(m.group()) if m else None


def _region_fields(bands_text, pricing, stores=()):
    """-> (kwargs para Device, region_basis) o (None, None) si no está en MX/US/CA."""
    basis = {r: b for r, b in classify_regions(bands_text, pricing, stores).items() if b}
    if not basis:
        return None, None
    return {"in_mx": "mx" in basis, "in_us": "us" in basis, "in_ca": "ca" in basis}, basis


def import_devices_from_sources(db: Session, csv_path: str, json_path: str):
    """
    Importa y normaliza teléfonos de processed_data2.csv y data.json a PostgreSQL,
    conservando SOLO los que están en el mercado de México, EE. UU. o Canadá
    (ver regions.py) y fueron lanzados desde settings.MIN_RELEASE_YEAR.
    Los teléfonos más antiguos NO entran al análisis: se guardan mínimos (marca, modelo, año)
    con is_legacy=True solo para poder responder "No compatible" si el usuario pregunta.
    Duplicados: (marca, modelo, ram, storage); el JSON solo aporta modelos que no estén en el CSV.
    Los archivos de datos originales NO se modifican.
    """
    # Centinela de idempotencia: si ya hay filas regionalizadas (region_basis no nulo),
    # la importación de esta versión ya se hizo y no se vuelve a tocar el catálogo.
    # (Antes se usaba "existe algún is_legacy", que fallaba si no había ninguno.)
    regionalized = db.query(Device).filter(Device.region_basis.isnot(None)).count()
    if regionalized:
        logger.info(f"Catálogo regionalizado ya importado ({regionalized} equipos con región). Se omite la importación.")
        return

    legacy = db.query(Device).count()
    if legacy:
        logger.warning(f"Catálogo de versión anterior ({legacy} equipos): se reimporta filtrado. "
                       "Se borra el detalle por dispositivo de análisis previos (los resúmenes se conservan).")
        db.query(AnalysisDevice).delete()
        db.query(Device).delete()
        db.commit()

    min_year = settings.MIN_RELEASE_YEAR
    logger.info(f"Importando catálogo MX/US/CA (año mínimo {min_year})...")
    skipped = {"viejo": 0, "estado": 0, "so": 0, "sin_region": 0, "duplicado": 0}
    legacy_seen: Set[Tuple] = set()

    def add_legacy(brand, model, year, os_type):
        """Teléfono demasiado antiguo: registro mínimo, sin regiones ni specs."""
        k = (brand, model.lower())
        if k in legacy_seen:
            return
        legacy_seen.add(k)
        devices_to_insert.append(Device(
            phone_brand=brand, phone_model=model, os_type=os_type, release_year=year,
            in_mx=False, in_us=False, in_ca=False, region_basis={}, is_legacy=True,
        ))

    seen_keys: Set[Tuple] = set()
    csv_models: Set[Tuple] = set()
    devices_to_insert = []

    # Índice del JSON (solo lectura): aporta bandas LTE, estado y precios por país
    json_items = []
    json_index = {}
    if os.path.exists(json_path):
        try:
            with open(json_path, mode="r", encoding="utf-8") as f:
                json_items = json.load(f)
        except Exception as e:
            logger.error(f"Error reading JSON {json_path}: {e}")
        for item in json_items:
            b = (item.get("phone_brand") or "").strip().lower()
            m = (item.get("phone_model") or "").strip().lower()
            if b and m:
                json_index.setdefault((b, m), item)

    # 1. CSV (fuente principal)
    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode="r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    brand = (row.get("phone_brand") or "").strip().lower()
                    model = (row.get("phone_model") or "").strip()
                    if not brand or not model:
                        continue
                    csv_models.add((brand, model.lower()))

                    year = clean_int(row.get("year")) or _year_from(row.get("launch_date"))
                    if year is None:
                        skipped["viejo"] += 1
                        continue

                    os_type = (row.get("os_type") or "").strip()
                    if os_type.lower() not in ("android", "ios"):
                        skipped["so"] += 1
                        continue

                    if year < min_year:
                        skipped["viejo"] += 1
                        add_legacy(brand, model, year, os_type)
                        continue

                    j = json_index.get((brand, model.lower())) or {}
                    jspecs = j.get("specs") or {}
                    status = (jspecs.get("Launch") or {}).get("Status")
                    if j and not is_active_status(status):
                        skipped["estado"] += 1
                        continue

                    flags, basis = _region_fields(
                        (jspecs.get("Network") or {}).get("4G bands"), j.get("pricing"), [row.get("store")]
                    )
                    if not flags:
                        skipped["sin_region"] += 1
                        continue

                    ram = clean_float(row.get("ram"))
                    storage = clean_float(row.get("storage"))
                    key = (brand, model.lower(), ram, storage)
                    if key in seen_keys:
                        skipped["duplicado"] += 1
                        continue
                    seen_keys.add(key)

                    os_version = (row.get("os_version") or "").strip()
                    devices_to_insert.append(Device(
                        phone_brand=brand,
                        phone_model=model,
                        ram_gb=ram,
                        storage_gb=storage,
                        os_type=os_type,
                        os_version=os_version,
                        os_version_num=clean_float(os_version),
                        cpu=(row.get("cpu") or "").strip() or None,
                        cpu_cores=clean_int(row.get("cpu_core")),
                        gpu=(row.get("gpu") or "").strip() or None,
                        gpu_company=(row.get("gpu_company") or "").strip() or None,
                        chipset=(row.get("chipset") or "").strip() or None,
                        display_resolution=(row.get("display_resolution") or "").strip() or None,
                        ppi_density=clean_int(row.get("ppi_density")),
                        battery_size=(row.get("battery_size") or "").strip() or None,
                        price_usd=clean_float(row.get("price_usd")),
                        price_range=(row.get("price_range") or "").strip() or None,
                        release_year=year,
                        raw_specs=dict(row),
                        region_basis=basis,
                        **flags,
                    ))
        except Exception as e:
            logger.error(f"Error reading CSV {csv_path}: {e}")

    # 2. JSON: solo modelos que NO están en el CSV
    for item in json_items:
        brand = (item.get("phone_brand") or "").strip().lower()
        model = (item.get("phone_model") or "").strip()
        if not brand or not model or (brand, model.lower()) in csv_models:
            continue
        specs = item.get("specs")
        if not isinstance(specs, dict):
            continue

        launch = specs.get("Launch") or {}
        year = _year_from(launch.get("Announced"))
        if year is None:
            skipped["viejo"] += 1
            continue

        platform = specs.get("Platform") or {}
        os_str = platform.get("OS") or ""
        low = os_str.lower()
        os_type = "Android" if "android" in low else ("iOS" if "ios" in low else None)
        if not os_type:
            skipped["so"] += 1
            continue

        if year < min_year:
            skipped["viejo"] += 1
            add_legacy(brand, model, year, os_type)
            continue
        if not is_active_status(launch.get("Status")):
            skipped["estado"] += 1
            continue

        mem_str = (specs.get("Memory") or {}).get("Internal") or ""
        if not isinstance(mem_str, str) or not mem_str:
            continue
        ram_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:GB|MB)\s*RAM", mem_str, re.I)
        storage_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:GB|TB|MB)(?!\s*RAM)", mem_str, re.I)
        ram = clean_float(ram_m.group(1)) if ram_m else None
        if ram_m and "MB" in ram_m.group(0).upper() and ram:
            ram = round(ram / 1024, 2)
        storage = clean_float(storage_m.group(1)) if storage_m else None
        if storage_m and "TB" in storage_m.group(0).upper() and storage:
            storage = storage * 1024
        if not ram and not storage:
            continue

        flags, basis = _region_fields((specs.get("Network") or {}).get("4G bands"), item.get("pricing"))
        if not flags:
            skipped["sin_region"] += 1
            continue

        key = (brand, model.lower(), ram, storage)
        if key in seen_keys:
            skipped["duplicado"] += 1
            continue
        seen_keys.add(key)

        # raw_specs reducido: se guardan solo secciones útiles, no el JSON completo
        raw = {k: specs.get(k) for k in ("Network", "Launch", "Platform", "Memory", "Display") if k in specs}
        devices_to_insert.append(Device(
            phone_brand=brand,
            phone_model=model,
            ram_gb=ram,
            storage_gb=storage,
            os_type=os_type,
            os_version=os_str[:100] or None,
            os_version_num=clean_float(os_str),
            cpu=(platform.get("CPU") or "")[:255] or None,
            cpu_cores=clean_int(platform.get("CPU")),
            gpu=(platform.get("GPU") or "")[:255] or None,
            chipset=(platform.get("Chipset") or "")[:255] or None,
            display_resolution=((specs.get("Display") or {}).get("Resolution") or "")[:100] or None,
            release_year=year,
            raw_specs={"phone_brand": brand, "phone_model": model, "specs": raw},
            region_basis=basis,
            **flags,
        ))

    logger.info(f"Descartados: {skipped}")
    for i in range(0, len(devices_to_insert), 1000):
        db.bulk_save_objects(devices_to_insert[i:i + 1000])
        db.commit()

    logger.info(
        "Importación completa. Activos: %d (MX=%d, US=%d, CA=%d) | antiguos (solo consulta): %d",
        db.query(Device).filter(Device.is_legacy.is_(False)).count(),
        db.query(Device).filter(Device.in_mx.is_(True)).count(),
        db.query(Device).filter(Device.in_us.is_(True)).count(),
        db.query(Device).filter(Device.in_ca.is_(True)).count(),
        db.query(Device).filter(Device.is_legacy.is_(True)).count(),
    )
