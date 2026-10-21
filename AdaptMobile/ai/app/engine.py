import httpx
import json
import logging
from typing import Dict, Any, List, Optional
from .config import settings
from .parser import parse_project_file
from .deepseek import deepseek

logger = logging.getLogger("ai_engine")


def display_name(brand: Optional[str], model: Optional[str]) -> str:
    """
    Nombre del dispositivo sin duplicar la marca.
    El dataset guarda marca="apple" y modelo="Apple iPhone 16 Pro", así que
    concatenarlos a lo bruto daría "Apple Apple iPhone 16 Pro".
    """
    b = (brand or "").strip()
    m = (model or "").strip()
    if not m:
        return b.capitalize()
    if b and m.lower().startswith(b.lower()):
        return m
    return f"{b.capitalize()} {m}".strip()

class AIEngine:
    def __init__(self):
        self.provider = settings.provider
        logger.info(f"Initialized AI Engine with provider: {self.provider}")

    def estimate_requirements(self, filename: str, content: str) -> Dict[str, Any]:
        """
        Estimates hardware and OS requirements based on project manifest.
        """
        parsed = parse_project_file(filename, content)
        
        # Base requirements
        min_ram = 3.0
        rec_ram = 4.0
        min_storage = 1.0
        min_cpu_cores = 4
        gpu_tier = "entry"
        graphics_api = "OpenGL ES 3.0"
        
        # OS versions
        min_android = 8.0
        min_ios = 13.0

        if parsed.get("min_android_sdk"):
            # Map SDK integer to Android Version (e.g. 21 -> 5.0, 26 -> 8.0, 28 -> 9.0, 29 -> 10.0, 30 -> 11.0, 33 -> 13.0, 34 -> 14.0)
            sdk_map = {
                21: 5.0, 22: 5.1, 23: 6.0, 24: 7.0, 25: 7.1,
                26: 8.0, 27: 8.1, 28: 9.0, 29: 10.0, 30: 11.0,
                31: 12.0, 32: 12.1, 33: 13.0, 34: 14.0, 35: 15.0
            }
            min_android = sdk_map.get(parsed["min_android_sdk"], float(parsed["min_android_sdk"]) - 19.0)
        
        if parsed.get("min_ios_sdk"):
            min_ios = float(parsed["min_ios_sdk"])

        framework = parsed["framework"]

        # Framework-specific adjustments
        if "React Native" in framework:
            min_ram = max(min_ram, 3.0)
            rec_ram = max(rec_ram, 6.0)
            min_storage = max(min_storage, 1.5)
            min_android = max(min_android, 8.0)
            min_ios = max(min_ios, 13.4)
            gpu_tier = "entry"
            graphics_api = "OpenGL ES 3.0 / Metal 2.0"
        elif "Flutter" in framework:
            min_ram = max(min_ram, 3.0)
            rec_ram = max(rec_ram, 4.0)
            min_storage = max(min_storage, 1.2)
            min_android = max(min_android, 8.0)
            min_ios = max(min_ios, 12.0)
            graphics_api = "Skia / Impeller (Vulkan & Metal)"
        elif "Unity" in framework or parsed["is_game_or_3d"]:
            min_ram = max(min_ram, 4.0)
            rec_ram = max(rec_ram, 8.0)
            min_storage = max(min_storage, 3.5)
            min_cpu_cores = 6
            min_android = max(min_android, 9.0)
            min_ios = max(min_ios, 14.0)
            gpu_tier = "mid"
            graphics_api = "Vulkan 1.1 / Metal 2.0"
        elif "Unreal" in framework:
            min_ram = max(min_ram, 6.0)
            rec_ram = max(rec_ram, 12.0)
            min_storage = max(min_storage, 6.0)
            min_cpu_cores = 8
            min_android = max(min_android, 10.0)
            min_ios = max(min_ios, 15.0)
            gpu_tier = "high"
            graphics_api = "Vulkan 1.2 / Metal 3.0"
        elif "Jetpack Compose" in framework:
            min_ram = max(min_ram, 3.5)
            rec_ram = max(rec_ram, 6.0)
            min_android = max(min_android, 8.0)
        
        # Heavy features modifiers
        if parsed["uses_ml"]:
            min_ram += 1.0
            rec_ram += 2.0
            min_cpu_cores = max(min_cpu_cores, 6)
            min_storage += 1.0
            gpu_tier = "mid" if gpu_tier == "entry" else gpu_tier
        
        if parsed["uses_camera_ar"]:
            min_ram += 0.5
            rec_ram += 1.5
            min_android = max(min_android, 8.0)
            min_ios = max(min_ios, 13.0)
            if gpu_tier == "entry":
                gpu_tier = "mid"
        
        if parsed["uses_heavy_media"]:
            min_ram += 0.5
            rec_ram += 1.0
            min_storage += 1.0

        project_name = parsed.get("project_name") or filename.split(".")[0].replace("-", " ").title()

        heuristic = {
            "project_name": project_name,
            "detected_tech": {
                "framework": parsed["framework"],
                "language": parsed["language"],
                "target_platforms": parsed["target_platforms"],
                "dependencies_count": len(parsed["dependencies"]),
                "heavy_features": parsed["heavy_features"],
                "format": parsed["format"]
            },
            "requirements": {
                "min_ram_gb": round(min_ram, 1),
                "rec_ram_gb": round(rec_ram, 1),
                "min_storage_gb": round(min_storage, 1),
                "min_cpu_cores": min_cpu_cores,
                "min_android_version": round(min_android, 1),
                "min_ios_version": round(min_ios, 1),
                "gpu_tier": gpu_tier,
                "graphics_api": graphics_api
            },
            "source": "heuristic"
        }

        # DeepSeek refina los numeros; sin key o si falla, se devuelve la heuristica intacta.
        return self._try_llm_estimate(filename, content, parsed, heuristic) or heuristic

    def generate_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receives summarized metrics and small candidate sample.
        Generates executive summary and optimization recommendations.
        """
        tech = payload.get("detected_tech", {})
        reqs = payload.get("requirements", {})
        stats = payload.get("stats", {})
        project_name = payload.get("project_name", "Proyecto Móvil")
        
        total = stats.get("total", 0)
        comp = stats.get("compatible", 0)
        lim = stats.get("limited", 0)
        incomp = stats.get("incompatible", 0)

        comp_pct = round((comp / total * 100) if total else 0, 1)
        lim_pct = round((lim / total * 100) if total else 0, 1)
        incomp_pct = round((incomp / total * 100) if total else 0, 1)

        framework = tech.get("framework", "Móvil")
        min_ram = reqs.get("min_ram_gb", 3.0)
        rec_ram = reqs.get("rec_ram_gb", 6.0)

        # Primary bottlenecks
        bottlenecks = []
        if incomp > 0:
            bottlenecks.append(f"Dispositivos con menos de {min_ram}GB de RAM sufrirán bloqueos por Out-Of-Memory (OOM).")
            bottlenecks.append(f"Modelos con versiones de SO inferiores a Android {reqs.get('min_android_version')} o iOS {reqs.get('min_ios_version')} quedan descartados por falta de APIs modernas.")
        if lim > 0:
            bottlenecks.append(f"Equipos con {min_ram}GB-{rec_ram}GB de RAM experimentarán caídas de frames y throttling térmico en sesiones prolongadas.")

        # Framework-specific recommendations
        recommendations = []
        if "React Native" in framework:
            recommendations.append({
                "category": "Motor JavaScript",
                "title": "Activar Hermes Engine y Nuevo Renderer (Fabric)",
                "detail": "Hermes reduce el consumo de memoria RAM en hasta un 40% y acelera el tiempo de arranque (TTI) en dispositivos de gama media y baja."
            })
            recommendations.append({
                "category": "Bundle & Assets",
                "title": "Optimización de imágenes con formatos WebP / AVIF",
                "detail": "Evita empaquetar bitmaps PNG/JPEG sin comprimir. Usar WebP reduce el uso de memoria en el heap gráfico un 35%."
            })
            recommendations.append({
                "category": "Compilación",
                "title": "Habilitar ProGuard / R8 en Android",
                "detail": "Elimina código muerto y reduce el tamaño del APK/AAB hasta en un 30%, facilitando la instalación en teléfonos con poco almacenamiento."
            })
        elif "Flutter" in framework:
            recommendations.append({
                "category": "Renderizado Gráfico",
                "title": "Aprovechar Impeller Engine",
                "detail": "Impeller elimina el shader jank al precompilar shaders en tiempo de construcción, asegurando 60 FPS estables en Android e iOS."
            })
            recommendations.append({
                "category": "Árbol de Widgets",
                "title": "Evitar rebuilds innecesarios con const constructors",
                "detail": "El uso constante de 'const' reduce la presión sobre el Garbage Collector de Dart en terminales con 3GB o 4GB de RAM."
            })
        elif "Unity" in framework or tech.get("is_game_or_3d"):
            recommendations.append({
                "category": "Texturas GPU",
                "title": "Compresión de texturas con ASTC",
                "detail": "ASTC es soportado por el 98% de teléfonos modernos y reduce el ancho de banda de memoria GPU hasta 4x."
            })
            recommendations.append({
                "category": "Shaders",
                "title": "Implementar Dynamic Resolution Scaling",
                "detail": "Permite escalar dinámicamente la resolución interna en dispositivos de gama de entrada para mantener la tasa de fotogramas."
            })
        else:
            recommendations.append({
                "category": "Memoria",
                "title": "Gestión activa de ciclo de vida en segundo plano",
                "detail": "Libera cachés de imágenes y conexiones cuando la aplicación pasa a onPause/onStop para evitar terminación por el kernel OOM killer."
            })
            recommendations.append({
                "category": "Almacenamiento",
                "title": "Carga diferida (Dynamic Feature Modules / On-Demand Assets)",
                "detail": "Descarga módulos pesados solo cuando el usuario los requiera, manteniendo la descarga inicial por debajo de 50MB."
            })

        region = payload.get("region") or "el mercado seleccionado"
        summary = (
            f"El proyecto '{project_name}' basado en {framework} presenta un índice de viabilidad del {comp_pct}% "
            f"en el catálogo de dispositivos de {region}. Un {lim_pct}% de los modelos podrá ejecutarlo con restricciones "
            f"o ajustes de calidad, mientras que un {incomp_pct}% no cumple con los requisitos mínimos de memoria ({min_ram}GB RAM) "
            f"o nivel de sistema operativo requerido."
        )

        deterministic = {
            "summary": summary,
            "bottlenecks": bottlenecks,
            "recommendations": recommendations
        }
        # DeepSeek redacta el informe ejecutivo; si falla se conserva el texto determinista.
        return self._try_llm_report(payload, deterministic, region)

    def ask_question(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Answers a user question regarding device compatibility.
        Takes verified device specs from PostgreSQL.
        """
        device = payload.get("device_specs")
        question = payload.get("question", "")
        reqs = payload.get("requirements", {})
        project_name = payload.get("project_name", "el proyecto")

        # Strict rule: If device was not found in database, do NOT invent data!
        if not device:
            return {
                "answer": (
                    "El modelo consultado no se encuentra en la base de datos verificada de AdaptMobile. "
                    "Para garantizar total precisión y no inventar especificaciones técnicas, "
                    "únicamente evaluamos dispositivos presentes en los registros oficiales importados."
                ),
                "device_found": False
            }

        brand = (device.get("phone_brand") or "").strip().capitalize()
        model = (device.get("phone_model") or "").strip()
        # El modelo del dataset ya suele incluir la marca ("Apple iPhone 16 Pro"):
        # así evitamos el "Apple Apple iPhone 16 Pro" en las respuestas.
        display = display_name(device.get("phone_brand"), model)
        ram = device.get("ram_gb", 0)
        storage = device.get("storage_gb", 0)
        os_name = device.get("os_type", "")
        os_ver = device.get("os_version", "")
        cpu = device.get("cpu", "No especificado")
        gpu = device.get("gpu", "No especificado")

        min_ram = reqs.get("min_ram_gb", 3.0)
        rec_ram = reqs.get("rec_ram_gb", 6.0)

        # Verdict evaluation
        verdict = "Compatible"
        reasons = []

        if ram < min_ram:
            verdict = "No compatible"
            reasons.append(f"La memoria RAM disponible ({ram} GB) es menor al requerimiento mínimo de {min_ram} GB.")
        elif ram < rec_ram:
            verdict = "Compatible con limitaciones"
            reasons.append(f"Cuenta con {ram} GB de RAM, alcanzando el mínimo ({min_ram} GB) pero por debajo de lo recomendado ({rec_ram} GB). Puede sufrir tirones o cierres si hay apps concurrentes.")
        else:
            reasons.append(f"Los {ram} GB de RAM satisfacen plenamente los requerimientos recomendados ({rec_ram} GB).")

        answer = (
            f"**Dispositivo:** {display}\n\n"
            f"**Especificaciones verificadas:**\n"
            f"- RAM: {ram} GB\n"
            f"- Almacenamiento: {storage} GB\n"
            f"- Sistema Operativo: {os_name} ({os_ver})\n"
            f"- CPU: {cpu}\n"
            f"- GPU: {gpu}\n\n"
            f"**Diagnóstico para {project_name}:** **{verdict}**\n\n"
            f"{' '.join(reasons)}"
        )

        deterministic = {
            "answer": answer,
            "verdict": verdict,
            "device_found": True,
            "device": {
                "brand": brand,
                "model": model,
                "ram": ram,
                "storage": storage,
                "os": f"{os_name} {os_ver}"
            }
        }
        # El veredicto determinista nunca se delega al LLM; DeepSeek solo redacta.
        return self._try_llm_answer(payload, device, reqs, deterministic)

    # ------------------------------------------------------------------ DeepSeek
    # El LLM NUNCA puede introducir valores absurdos: todo número se acota a un
    # rango físico razonable y, ante cualquier duda, manda la heurística.
    @staticmethod
    def _num(value, fallback: float, low: float, high: float) -> float:
        try:
            num = float(value)
        except (TypeError, ValueError):
            return fallback
        return round(min(max(num, low), high), 1)

    def _llm_estimate_prompt(self, filename: str, content: str, parsed: dict):
        deps = parsed.get("dependencies") or []
        system = (
            "Eres un ingeniero de rendimiento movil. Estimas los requisitos MINIMOS de hardware "
            "para ejecutar un proyecto movil a partir de UN archivo de manifiesto. "
            "Responde SIEMPRE en JSON valido y sin texto adicional, con esta forma exacta: "
            '{"min_ram_gb": number, "rec_ram_gb": number, "min_storage_gb": number, '
            '"min_cpu_cores": integer, "min_android_version": number, "min_ios_version": number, '
            '"gpu_tier": "entry"|"mid"|"high", "graphics_api": string, "reasoning": string}. '
            "Se realista y conservador: la mayoria de las apps moviles necesitan entre 2 y 6 GB de RAM. "
            "No inventes datos que el archivo no permita deducir."
        )
        user = (
            f"Archivo: {filename}\n"
            f"Framework detectado por el parser deterministico: {parsed.get('framework')}\n"
            f"Plataformas objetivo: {parsed.get('target_platforms')}\n"
            f"minSdk Android: {parsed.get('min_android_sdk')} | min iOS: {parsed.get('min_ios_sdk')}\n"
            f"Funciones pesadas: {parsed.get('heavy_features')}\n"
            f"Dependencias ({len(deps)}): {', '.join(deps[:40])}\n\n"
            f"--- Contenido del archivo (recortado) ---\n{content[:4000]}"
        )
        return system, user

    def _try_llm_estimate(self, filename: str, content: str, parsed: dict, heuristic: dict) -> Optional[dict]:
        """Refina los requerimientos con DeepSeek. Devuelve None para usar la heurística."""
        if not deepseek.available():
            if deepseek.enabled:
                logger.info("AI_PROVIDER=deepseek sin API key util: se usa la heuristica determinista.")
            return None

        system, user = self._llm_estimate_prompt(filename, content, parsed)
        data = deepseek.chat_json(system, user, max_tokens=600)
        if not data:
            return None

        base = heuristic["requirements"]
        tier = str(data.get("gpu_tier") or base["gpu_tier"]).strip().lower()
        reqs = {
            "min_ram_gb": self._num(data.get("min_ram_gb"), base["min_ram_gb"], 1.0, 16.0),
            "rec_ram_gb": self._num(data.get("rec_ram_gb"), base["rec_ram_gb"], 1.0, 16.0),
            "min_storage_gb": self._num(data.get("min_storage_gb"), base["min_storage_gb"], 0.5, 32.0),
            "min_cpu_cores": int(self._num(data.get("min_cpu_cores"), base["min_cpu_cores"], 2, 16)),
            "min_android_version": self._num(data.get("min_android_version"), base["min_android_version"], 4.0, 16.0),
            "min_ios_version": self._num(data.get("min_ios_version"), base["min_ios_version"], 8.0, 20.0),
            "gpu_tier": tier if tier in ("entry", "mid", "high") else base["gpu_tier"],
            "graphics_api": str(data.get("graphics_api") or base["graphics_api"])[:120],
        }
        if reqs["rec_ram_gb"] < reqs["min_ram_gb"]:
            reqs["rec_ram_gb"] = reqs["min_ram_gb"]

        logger.info("Requerimientos refinados con DeepSeek (%s): RAM min %s GB.",
                    settings.llm_model, reqs["min_ram_gb"])
        result = dict(heuristic)
        result["requirements"] = reqs
        result["source"] = "deepseek"
        result["reasoning"] = str(data.get("reasoning") or "")[:500]
        return result

    def _try_llm_report(self, payload: Dict[str, Any], deterministic: dict, region: str) -> dict:
        """Redacta el informe ejecutivo con DeepSeek usando solo las métricas recibidas."""
        if not deepseek.available():
            return deterministic

        system = (
            "Eres un arquitecto de rendimiento movil. Redactas el resumen ejecutivo y las "
            "recomendaciones de optimizacion de un informe de compatibilidad de dispositivos. "
            "Responde SOLO en JSON valido con esta forma exacta: "
            '{"summary": string, "bottlenecks": [string], '
            '"recommendations": [{"category": string, "title": string, "detail": string}]}. '
            "Escribe en espanol tecnico, maximo 3 cuellos de botella y 3 recomendaciones concretas. "
            "Usa EXCLUSIVAMENTE los datos entregados: no inventes dispositivos, modelos ni cifras."
        )
        user = json.dumps({
            "proyecto": payload.get("project_name"),
            "mercado": region,
            "tecnologias": payload.get("detected_tech"),
            "requisitos_estimados": payload.get("requirements"),
            "estadisticas_de_compatibilidad": payload.get("stats"),
            "dispositivos_de_muestra": payload.get("sample_devices"),
            "cuellos_de_botella_deterministas": deterministic.get("bottlenecks"),
        }, ensure_ascii=False)

        data = deepseek.chat_json(system, user, max_tokens=settings.deepseek_max_tokens)
        if not data:
            return deterministic

        summary = str(data.get("summary") or "").strip()
        recs = [r for r in (data.get("recommendations") or []) if isinstance(r, dict) and r.get("title")]
        if not summary or not recs:
            logger.warning("DeepSeek devolvio un informe incompleto; se usa el determinista.")
            return deterministic

        bottlenecks = data.get("bottlenecks") or deterministic.get("bottlenecks") or []
        return {
            "summary": summary[:2000],
            "bottlenecks": [str(b)[:400] for b in bottlenecks][:5],
            "recommendations": [
                {
                    "category": str(r.get("category") or "Optimización")[:80],
                    "title": str(r.get("title"))[:200],
                    "detail": str(r.get("detail") or "")[:800],
                }
                for r in recs[:5]
            ],
            "source": "deepseek",
        }

    def _try_llm_answer(self, payload: Dict[str, Any], device: dict, reqs: dict, deterministic: dict) -> dict:
        """Redacta la respuesta al usuario anclada a las specs verificadas de PostgreSQL."""
        if not deepseek.available():
            return deterministic

        system = (
            "Eres el asistente tecnico de AdaptMobile. Explicas si un proyecto movil correra en un "
            "telefono concreto usando SOLO las especificaciones verificadas que se te entregan. "
            "Esta PROHIBIDO inventar, estimar o completar especificaciones que no aparezcan en los datos. "
            "Responde en espanol, en markdown breve (maximo 180 palabras), empezando con '**Dispositivo:**' "
            "usando el valor exacto de 'nombre_para_mostrar' (no repitas la marca), "
            "y cerrando con un diagnostico explicito: Compatible, Compatible con limitaciones o No compatible."
        )
        user = json.dumps({
            "proyecto": payload.get("project_name"),
            "requisitos_del_proyecto": reqs,
            "especificaciones_verificadas": device,
            "nombre_para_mostrar": display_name(device.get("phone_brand"), device.get("phone_model")),
            "pregunta_del_usuario": payload.get("question"),
            "diagnostico_determinista_obligatorio": deterministic.get("verdict"),
        }, ensure_ascii=False)

        text = deepseek.chat_text(system, user, max_tokens=700)
        if not text or len(text.strip()) < 20:
            return deterministic

        result = dict(deterministic)
        result["answer"] = text.strip()[:4000]
        result["source"] = "deepseek"
        return result


engine = AIEngine()
