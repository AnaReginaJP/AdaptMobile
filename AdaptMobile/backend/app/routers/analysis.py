from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from typing import Optional, List
import logging
import re

from ..database import get_db
from ..models import User, Device, Analysis, AnalysisDevice, Question
from ..schemas import AnalysisDetailOut, AnalysisSummaryOut, QuestionCreate, QuestionOut, AnalysisDeviceOut
from ..auth import get_current_user
from ..ai_client import ai_client
from ..regions import normalize_region, region_attr, REGION_NAMES
from ..config import settings
from ..telemetry import credits_available, credits_exhausted, log_funnel_event, log_usage_event

logger = logging.getLogger("analysis_router")

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

ALLOWED_EXTENSIONS = {
    ".json", ".gradle", ".kts", ".xml", ".yaml", ".yml",
    ".md", ".txt", ".lock", ".swift", ".podspec", ".pbxproj",
    ".godot", ".asset", ".ini", ".toml"
}

MAX_FILE_SIZE = 10 * 1024 * 1024 # 10 MB

def _display_name(dev) -> str:
    b, m = dev.phone_brand or "", dev.phone_model or ""
    return m if m.lower().startswith(b.lower()) else f"{b.title()} {m}".strip()


def _local_answer(analysis, device, region: str) -> str:
    """
    Respuesta de respaldo cuando el microservicio de IA no responde.
    Usa EXCLUSIVAMENTE especificaciones verificadas de PostgreSQL: no inventa datos.
    """
    if device is None:
        return (
            "El modelo consultado no se encuentra en la base de datos verificada de AdaptMobile "
            f"({REGION_NAMES[region]}). Para no inventar especificaciones técnicas, solo evaluamos "
            "dispositivos presentes en los registros oficiales importados."
        )

    reqs = analysis.requirements or {}
    min_ram = reqs.get("min_ram_gb", 3.0)
    rec_ram = reqs.get("rec_ram_gb", 6.0)
    ram = device.ram_gb or 0

    if ram < min_ram:
        verdict = "No compatible"
        why = f"La memoria RAM disponible ({ram} GB) es menor al requerimiento mínimo de {min_ram} GB."
    elif ram < rec_ram:
        verdict = "Compatible con limitaciones"
        why = (f"Cuenta con {ram} GB de RAM: alcanza el mínimo ({min_ram} GB) pero queda por debajo "
               f"de lo recomendado ({rec_ram} GB).")
    else:
        verdict = "Compatible"
        why = f"Sus {ram} GB de RAM cubren plenamente lo recomendado ({rec_ram} GB)."

    return (
        f"**Dispositivo:** {_display_name(device)}\n\n"
        f"**Especificaciones verificadas:** RAM {ram} GB · Almacenamiento {device.storage_gb} GB · "
        f"{device.os_type} {device.os_version or ''} · CPU {device.cpu or 'no especificada'}\n\n"
        f"**Diagnóstico para {analysis.project_name}:** **{verdict}**\n\n{why}"
    )


def _find_device_in_question(db: Session, question: str, region: str):
    """
    Busca en PostgreSQL el modelo mencionado en la pregunta (gana el nombre más largo).
    Devuelve (activo_en_la_region, otro): 'otro' es un teléfono antiguo o de otra región.
    """
    q = question.lower()
    attr = region_attr(region)
    rows = db.query(Device.id, Device.phone_brand, Device.phone_model, Device.is_legacy, getattr(Device, attr)).all()
    best = None
    for did, brand, model, legacy, in_reg in rows:
        full = (model or "").lower().strip()
        names = {full}
        b = (brand or "").lower()
        if b and full.startswith(b):
            names.add(full[len(b):].strip())
        active = bool(in_reg and not legacy)
        for n in names:
            if len(n) < 4 or n not in q:
                continue
            if not re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", q):
                continue
            rank = (len(n), active)
            if best is None or rank > best[0]:
                best = (rank, did, active)
    if not best:
        return None, None
    dev = db.get(Device, best[1])
    return (dev, None) if best[2] else (None, dev)


@router.post("/upload")
async def analyze_project_file(
    file: UploadFile = File(...),
    region: str = Form("mx"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        region = normalize_region(region)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 1. Check user credit limits (2 free per month, reinicio mensual automático)
    if not credits_available(db, current_user):
        log_funnel_event(db, "limit_reached", current_user.id)
        raise credits_exhausted(current_user)

    # 2. File validation
    filename = file.filename or "unknown_file"
    file_ext = "." + filename.split(".")[-1].lower() if "." in filename else ""
    if file_ext not in ALLOWED_EXTENSIONS and not filename.lower() in ["podfile", "dockerfile"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no admitido. Sube un manifiesto o configuración ({', '.join(sorted(ALLOWED_EXTENSIONS))})"
        )

    content_bytes = await file.read()
    if len(content_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo excede el tamaño máximo permitido (10 MB)."
        )

    try:
        content_str = content_bytes.decode("utf-8", errors="replace")
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo decodificar el contenido del archivo como texto.")

    # 3. Call AI Service: Estimate Requirements
    try:
        est_result = await ai_client.estimate_requirements(filename, content_str)
    except Exception as e:
        logger.error(f"Error calling AI service for requirements: {e}")
        raise HTTPException(status_code=502, detail=f"Error al comunicar con el servicio de IA: {str(e)}")

    project_name = est_result.get("project_name", filename)
    detected_tech = est_result.get("detected_tech", {})
    reqs = est_result.get("requirements", {})

    target_platforms = [p.lower() for p in detected_tech.get("target_platforms", ["android", "ios"])]
    min_ram = reqs.get("min_ram_gb", 3.0)
    rec_ram = reqs.get("rec_ram_gb", 6.0)
    min_android = reqs.get("min_android_version", 8.0)
    min_ios = reqs.get("min_ios_version", 13.0)
    min_storage = reqs.get("min_storage_gb", 1.0)
    min_cpu_cores = reqs.get("min_cpu_cores", 4)

    # 4. Filter and classify devices in PostgreSQL (avoid sending all phones to AI!)
    # Solo dispositivos del mercado elegido (MX / US / CA): el resto ni se evalúa
    all_devices = db.query(Device).filter(getattr(Device, region_attr(region)).is_(True)).all()
    if not all_devices:
        raise HTTPException(status_code=500, detail=f"No hay dispositivos para {REGION_NAMES[region]}. Verifique la importación de datos.")

    evaluations = []
    comp_count = 0
    lim_count = 0
    incomp_count = 0

    sample_comp = None
    sample_lim = None
    sample_incomp = None

    for dev in all_devices:
        os_type_lower = (dev.os_type or "").lower()
        status_val = "compatible"
        reasons = []

        # Check OS Platform
        if "ios" in os_type_lower and "ios" not in target_platforms:
            status_val = "incompatible"
            reasons.append("Proyecto no dirigido a plataforma iOS.")
        elif "android" in os_type_lower and "android" not in target_platforms:
            status_val = "incompatible"
            reasons.append("Proyecto no dirigido a plataforma Android.")

        # Check OS Version
        if status_val != "incompatible":
            if "android" in os_type_lower and dev.os_version_num is not None:
                if dev.os_version_num < min_android:
                    status_val = "incompatible"
                    reasons.append(f"Versión de Android ({dev.os_version_num}) inferior a mínima ({min_android}).")
            elif "ios" in os_type_lower and dev.os_version_num is not None:
                if dev.os_version_num < min_ios:
                    status_val = "incompatible"
                    reasons.append(f"Versión de iOS ({dev.os_version_num}) inferior a mínima ({min_ios}).")

        # Check RAM
        if status_val != "incompatible":
            if dev.ram_gb is not None:
                if dev.ram_gb < min_ram:
                    status_val = "incompatible"
                    reasons.append(f"RAM insuficiente ({dev.ram_gb} GB vs mín {min_ram} GB).")
                elif dev.ram_gb < rec_ram:
                    status_val = "limited"
                    reasons.append(f"RAM justa ({dev.ram_gb} GB). Recomendado {rec_ram} GB.")
                else:
                    reasons.append(f"RAM óptima ({dev.ram_gb} GB).")
            else:
                status_val = "limited"
                reasons.append("RAM no especificada por fabricante.")

        # Check Storage
        if status_val != "incompatible" and dev.storage_gb is not None:
            if dev.storage_gb < min_storage:
                status_val = "incompatible"
                reasons.append(f"Almacenamiento bajo ({dev.storage_gb} GB vs mín {min_storage} GB).")

        # Check CPU Cores
        if status_val == "compatible" and dev.cpu_cores is not None:
            if dev.cpu_cores < min_cpu_cores:
                status_val = "limited"
                reasons.append(f"CPU de {dev.cpu_cores} núcleos (recomendado {min_cpu_cores}+).")

        # Tallies
        if status_val == "compatible":
            comp_count += 1
            if not sample_comp: sample_comp = {"brand": dev.phone_brand, "model": dev.phone_model, "ram": dev.ram_gb}
        elif status_val == "limited":
            lim_count += 1
            if not sample_lim: sample_lim = {"brand": dev.phone_brand, "model": dev.phone_model, "ram": dev.ram_gb}
        else:
            incomp_count += 1
            if not sample_incomp: sample_incomp = {"brand": dev.phone_brand, "model": dev.phone_model, "ram": dev.ram_gb}

        final_reason = " ".join(reasons) if reasons else "Cumple todos los requisitos de hardware y sistema operativo."
        evaluations.append((dev.id, status_val, final_reason))

    total_devices = len(all_devices)
    stats = {
        "total": total_devices,
        "compatible": comp_count,
        "limited": lim_count,
        "incompatible": incomp_count,
        "compatible_pct": round((comp_count / total_devices * 100), 1),
        "limited_pct": round((lim_count / total_devices * 100), 1),
        "incompatible_pct": round((incomp_count / total_devices * 100), 1)
    }

    # 5. Token Reduction: Send ONLY minimal summary packet to AI for report generation
    report_payload = {
        "project_name": project_name,
        "detected_tech": detected_tech,
        "requirements": reqs,
        "region": REGION_NAMES[region],
        "stats": stats,
        "sample_devices": [d for d in [sample_comp, sample_lim, sample_incomp] if d]
    }

    try:
        ai_report = await ai_client.generate_report(report_payload)
    except Exception as e:
        logger.warning(f"AI report generation failed, using fallback summary: {e}")
        ai_report = {
            "summary": f"Análisis de {project_name}: {comp_count} compatibles, {lim_count} con limitaciones, {incomp_count} incompatibles.",
            "bottlenecks": [f"RAM mínima requerida: {min_ram} GB."],
            "recommendations": []
        }

    # 6. Save in PostgreSQL
    analysis = Analysis(
        user_id=current_user.id,
        filename=filename,
        file_type=file_ext,
        project_name=project_name,
        region=region,
        tech_stack=detected_tech,
        requirements=reqs,
        summary=ai_report.get("summary"),
        recommendations=ai_report.get("recommendations"),
        stats=stats
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    # Batch save device evaluations
    batch_devices = [
        AnalysisDevice(analysis_id=analysis.id, device_id=dev_id, status=st, reason=rs)
        for dev_id, st, rs in evaluations
    ]
    db.bulk_save_objects(batch_devices)

    # 7. Increment user credits usage (y queda registrado en usage_events)
    current_user.credits_used += 1
    db.commit()
    log_usage_event(db, current_user, "analysis", analysis.id)

    return {
        "id": analysis.id,
        "project_name": project_name,
        "filename": filename,
        "file_type": file_ext,
        "region": region,
        "tech_stack": detected_tech,
        "requirements": reqs,
        "summary": analysis.summary,
        "bottlenecks": ai_report.get("bottlenecks", []),
        "recommendations": analysis.recommendations,
        "stats": stats,
        "credits_used": current_user.credits_used,
        "credits_limit": current_user.credits_limit
    }

@router.get("", response_model=List[AnalysisSummaryOut])
def get_user_analyses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists history of analyses performed by the user."""
    analyses = db.query(Analysis).filter(Analysis.user_id == current_user.id).order_by(desc(Analysis.created_at)).all()
    return analyses

@router.get("/{analysis_id}")
def get_analysis_detail(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: Optional[str] = Query(None, alias="status"),
    brand: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=100)
):
    """Returns analysis detail with paginated and filtered device compatibility results."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")

    if current_user.role != "admin" and analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver este análisis")

    # Query evaluated devices
    q = db.query(AnalysisDevice).join(Device).filter(AnalysisDevice.analysis_id == analysis_id)

    if status_filter:
        q = q.filter(AnalysisDevice.status == status_filter.lower())
    if brand:
        q = q.filter(Device.phone_brand.ilike(f"%{brand}%"))
    if search:
        search_fmt = f"%{search}%"
        q = q.filter(or_(Device.phone_model.ilike(search_fmt), Device.phone_brand.ilike(search_fmt)))

    total_filtered = q.count()
    device_rows = q.offset(skip).limit(limit).all()

    devices_data = [
        {
            "id": row.id,
            "device_id": row.device_id,
            "status": row.status,
            "reason": row.reason,
            "device": {
                "id": row.device.id,
                # Nombre listo para mostrar, sin duplicar la marca ("Apple Apple iPhone...")
                "display_name": _display_name(row.device),
                "phone_brand": row.device.phone_brand,
                "phone_model": row.device.phone_model,
                "ram_gb": row.device.ram_gb,
                "storage_gb": row.device.storage_gb,
                "os_type": row.device.os_type,
                "os_version": row.device.os_version,
                "cpu": row.device.cpu,
                "gpu": row.device.gpu,
                "chipset": row.device.chipset,
                "display_resolution": row.device.display_resolution,
                "price_usd": row.device.price_usd,
                "release_year": row.device.release_year
            }
        }
        for row in device_rows
    ]

    return {
        "id": analysis.id,
        "project_name": analysis.project_name,
        "filename": analysis.filename,
        "file_type": analysis.file_type,
        "tech_stack": analysis.tech_stack,
        "requirements": analysis.requirements,
        "summary": analysis.summary,
        "recommendations": analysis.recommendations,
        "stats": analysis.stats,
        "created_at": analysis.created_at,
        "devices_pagination": {
            "total": total_filtered,
            "skip": skip,
            "limit": limit
        },
        "devices": devices_data
    }

@router.post("/{analysis_id}/ask", response_model=QuestionOut)
async def ask_analysis_question(
    analysis_id: int,
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Asks a question about the analysis.
    Searches phone in PostgreSQL first. If not found, informs without inventing.
    Uses 1 credit.
    """
    if not credits_available(db, current_user):
        log_funnel_event(db, "limit_reached", current_user.id)
        raise credits_exhausted(current_user)

    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")

    if current_user.role != "admin" and analysis.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este análisis")

    # Search for mentioned device in PostgreSQL first (solo en la región del análisis)
    region = analysis.region or "mx"
    in_region = getattr(Device, region_attr(region)).is_(True)
    target_device = None
    other_device = None  # existe en la base pero es antiguo o de otra región
    device_name = payload.device_name

    if device_name:
        term = f"%{device_name.strip()}%"
        match = or_(Device.phone_model.ilike(term), Device.phone_brand.ilike(term))
        target_device = db.query(Device).filter(match, in_region).first()
        if not target_device:
            other_device = db.query(Device).filter(match).order_by(Device.is_legacy.desc()).first()
    else:
        # 1) Modelo concreto mencionado en la pregunta (incluye teléfonos antiguos)
        target_device, other_device = _find_device_in_question(db, payload.question, region)
        # 2) Respaldo anterior: primera coincidencia por marca dentro de la región
        if not target_device and not other_device:
            words = payload.question.lower()
            brands = ["iphone", "samsung", "xiaomi", "motorola", "google", "pixel", "oneplus", "huawei", "sony", "oppo", "realme", "nokia", "honor"]
            for b in brands:
                if b in words:
                    target_device = db.query(Device).filter(
                        or_(Device.phone_model.ilike(f"%{b}%"), Device.phone_brand.ilike(f"%{b}%")), in_region
                    ).first()
                    if target_device:
                        break
        found = target_device or other_device
        if found:
            device_name = _display_name(found)

    # Respuesta automática (sin IA, 0 tokens) si el modelo es antiguo o no es de la región
    blocked_answer = None
    if not target_device and other_device is not None:
        if other_device.is_legacy:
            blocked_answer = (
                f"No compatible. El {_display_name(other_device)} ({other_device.release_year}) "
                f"tiene {settings.MAX_AGE_YEARS} años o más de antigüedad, por lo que AdaptMobile "
                "lo marca automáticamente como No compatible, sin importar la región."
            )
        else:
            blocked_answer = (
                f"El {_display_name(other_device)} no está catalogado para {REGION_NAMES[region]}. "
                "AdaptMobile solo evalúa los dispositivos del mercado seleccionado. "
                "Crea otro análisis eligiendo la región correspondiente."
            )

    device_specs = None
    if target_device:
        device_specs = {
            "phone_brand": target_device.phone_brand,
            "phone_model": target_device.phone_model,
            "ram_gb": target_device.ram_gb,
            "storage_gb": target_device.storage_gb,
            "os_type": target_device.os_type,
            "os_version": target_device.os_version,
            "cpu": target_device.cpu,
            "gpu": target_device.gpu
        }

    if blocked_answer:
        answer_text = blocked_answer
    else:
        # Call AI microservice with verified data (minimal tokens!)
        try:
            ai_resp = await ai_client.ask_question({
                "project_name": analysis.project_name,
                "requirements": analysis.requirements or {},
                "device_specs": device_specs,
                "question": payload.question
            })
            answer_text = ai_resp.get("answer", "No se pudo generar respuesta.")
        except Exception as e:
            # El servicio de IA no respondió: contestamos con los datos verificados,
            # sin inventar nada y sin gastar tokens.
            logger.warning(f"Servicio de IA no disponible ({e}); respuesta local con datos verificados.")
            answer_text = _local_answer(analysis, target_device, region)

    # Save question
    q_record = Question(
        analysis_id=analysis_id,
        user_id=current_user.id,
        device_name=device_name,
        question=payload.question,
        answer=answer_text
    )
    db.add(q_record)

    current_user.credits_used += 1
    db.commit()
    db.refresh(q_record)
    log_usage_event(db, current_user, "question", analysis_id)

    return q_record

@router.get("/{analysis_id}/questions", response_model=List[QuestionOut])
def get_analysis_questions(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves all Q&A history for a specific analysis."""
    questions = db.query(Question).filter(Question.analysis_id == analysis_id).order_by(Question.created_at.asc()).all()
    return questions
