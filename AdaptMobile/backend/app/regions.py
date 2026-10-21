"""
Clasificación de dispositivos por mercado (México, Estados Unidos, Canadá).

Reglas, en orden de fuerza de la evidencia:
  1. VENTA: el dataset muestra precio/tienda en ese país (data.json -> "pricing",
     processed_data2.csv -> "store"). El dataset NO trae datos de venta de México.
  2. RED: el teléfono lista las bandas LTE necesarias para operar en las redes
     de ese país (REGION_LTE_RULES). Es evidencia técnica, no de venta oficial.

REGION_LTE_RULES es un supuesto editable (no viene en los datos): cada región
requiere TODOS los grupos, y cada grupo se cumple con CUALQUIERA de sus bandas.
"""
import re
from typing import Dict, Iterable, Optional, Set

REGIONS = ("mx", "us", "ca")

REGION_LTE_RULES: Dict[str, list] = {
    "mx": [{2}, {4, 66}, {5, 7, 28}],
    "us": [{2}, {4, 66}, {12, 13, 17, 71}],
    "ca": [{2}, {4, 66}, {7}, {12, 17, 71}],
}

# Claves de "pricing" (data.json) y tiendas del CSV que prueban venta en el país
SOLD_PRICING_KEYS = {"us": "United States", "ca": "Canada"}
SOLD_CSV_STORES = {"us": {"amazon us", "best buy"}}

ACTIVE_STATUS_PREFIXES = ("available", "discontinued")

_BAND_RE = re.compile(r"\b(\d{1,2})\b")


def parse_lte_bands(text: Optional[str]) -> Set[int]:
    """'1, 2, 3, 4 - A3293' -> {1,2,3,4}. Ignora códigos de modelo (A3293)."""
    if not text or not isinstance(text, str):
        return set()
    return {int(b) for b in _BAND_RE.findall(text)}


def bands_match(region: str, bands: Set[int]) -> bool:
    return bool(bands) and all(bands & group for group in REGION_LTE_RULES[region])


def is_active_status(status: Optional[str]) -> bool:
    return bool(status) and status.strip().lower().startswith(ACTIVE_STATUS_PREFIXES)


def classify_regions(
    lte_bands_text: Optional[str],
    pricing: Optional[dict] = None,
    csv_stores: Iterable[str] = (),
) -> Dict[str, Optional[str]]:
    """Devuelve {'mx': 'red'|None, 'us': 'venta'|'red'|None, 'ca': ...}."""
    bands = parse_lte_bands(lte_bands_text)
    stores = {s.strip().lower() for s in csv_stores if s}
    pricing = pricing or {}
    out: Dict[str, Optional[str]] = {}
    for r in REGIONS:
        sold = (
            SOLD_PRICING_KEYS.get(r) in pricing
            or bool(stores & SOLD_CSV_STORES.get(r, set()))
        )
        if sold:
            out[r] = "venta"
        elif bands_match(r, bands):
            out[r] = "red"
        else:
            out[r] = None
    return out


REGION_NAMES = {"mx": "México", "us": "Estados Unidos", "ca": "Canadá"}


def normalize_region(value: Optional[str], default: str = "mx") -> str:
    """Valida el código de región ('mx' | 'us' | 'ca'). Lanza ValueError si no es válido."""
    r = (value or default).strip().lower()
    if r not in REGIONS:
        raise ValueError(f"Región no válida: {value!r}. Usa mx, us o ca.")
    return r


def region_attr(region: str) -> str:
    """Nombre de la columna booleana de Device para la región."""
    return f"in_{normalize_region(region)}"
