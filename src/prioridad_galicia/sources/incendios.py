"""Historial y validación con perímetros EFFIS.

Incendib está en pausa y la serie municipal abierta de la Xunta termina en
2006. EFFIS es la fuente espacial abierta que sí se puede agregar al municipio
sin inventar el cruce. El historial del índice acaba el 31-12-2024; 2025 y
2026 se reservan para la validación.
"""

from __future__ import annotations

import logging

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
from shapely.validation import make_valid

from prioridad_galicia.config import (
    CRS_TRABAJO,
    EFFIS_BURNT,
    HIST_FIN,
    HIST_INICIO,
    PROVINCIAS_EFFIS,
    VAL_FIN,
    VAL_INICIO,
)
from prioridad_galicia.http_client import SESION, obtener_json

logger = logging.getLogger(__name__)


def anadir_incendios(municipios: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, dict]:
    meta: dict = {"intentos": intentar_fuentes_bloqueadas()}
    historico = descargar_perimetros(HIST_INICIO, HIST_FIN)
    validacion = descargar_perimetros(VAL_INICIO, VAL_FIN)
    salida = municipios.copy()
    hist = agregar(historico, salida, prefijo="hist")
    val = agregar(validacion, salida, prefijo="val")
    salida = salida.merge(hist, on="codigo_ine", how="left")
    salida = salida.merge(val, on="codigo_ine", how="left")
    for columna in ("n_incendios_hist", "ha_quemadas_hist", "n_incendios_val", "ha_quemadas_val"):
        salida[columna] = salida[columna].fillna(0.0)
    salida["ha_quemadas_1000ha_hist"] = salida["ha_quemadas_hist"] / (salida["area_ha"] / 1000.0)
    meta.update(
        {
            "fuente_historial": "EFFIS burnt areas API (Copernicus), agregada por intersección municipal",
            "fuente_validacion": "EFFIS burnt areas API, campañas 2025-2026",
            "incendios_hist": int(historico["id"].nunique()) if len(historico) else 0,
            "incendios_val": int(validacion["id"].nunique()) if len(validacion) else 0,
            "nota": (
                "Incendib no ofrece descarga (pausa). EGIF no tiene volcado abierto por municipio. "
                "La serie municipal de la Xunta/IGE en datos abiertos cubre 2001-2006 y no se mezcla "
                "con este historial para no cambiar de definición a mitad de la serie."
            ),
        }
    )
    logger.info(
        "EFFIS: %s perímetros de historial y %s de validación",
        meta["incendios_hist"],
        meta["incendios_val"],
    )
    return salida, meta


def intentar_fuentes_bloqueadas() -> dict:
    """Registra el estado real de Incendib y del CSV municipal de la Xunta. No fabrica filas."""
    estado = {}
    for nombre, url in {
        "incendib": "https://incendib.es/",
        "xunta_municipal_2001_2006": (
            "https://abertos.xunta.gal/catalogo/economia-empresa-emprego/-/dataset/0147/"
            "incendios-forestais/101/acceso-aos-datos.csv"
        ),
    }.items():
        try:
            respuesta = SESION.get(url, timeout=25, allow_redirects=True)
            estado[nombre] = {"url": url, "http": respuesta.status_code, "bytes": len(respuesta.content)}
            if nombre == "incendib" and "pausa" in respuesta.text.lower():
                estado[nombre]["nota"] = (
                    "La portada responde, pero anuncia que Incendib está en pausa. No hay CSV ni GeoJSON."
                )
        except Exception as exc:  # noqa: BLE001 - el fallo de la fuente es un dato, no un aborto
            estado[nombre] = {"url": url, "error": str(exc)}
    return estado


def descargar_perimetros(inicio: str, fin: str) -> gpd.GeoDataFrame:
    filas = []
    vistos: set[int] = set()
    for provincia in PROVINCIAS_EFFIS:
        offset = 0
        while True:
            payload = obtener_json(
                EFFIS_BURNT,
                params={
                    "province": provincia,
                    "firedate__gte": f"{inicio}T00:00:00",
                    "firedate__lte": f"{fin}T23:59:59",
                    "limit": 200,
                    "offset": offset,
                },
                timeout=120,
            )
            lote = payload.get("results") or []
            for item in lote:
                identificador = item.get("id")
                if identificador in vistos or not item.get("shape"):
                    continue
                vistos.add(identificador)
                try:
                    geometria = shape(item["shape"])
                except Exception:
                    continue
                if geometria.is_empty:
                    continue
                if not geometria.is_valid:
                    geometria = make_valid(geometria)
                filas.append(
                    {
                        "id": identificador,
                        "fecha": item.get("firedate"),
                        "provincia_effis": item.get("province"),
                        "municipio_effis": item.get("commune"),
                        "area_ha_effis": _float(item.get("area_ha")),
                        "geometry": geometria,
                    }
                )
            if not payload.get("next") or not lote:
                break
            offset += 200
    if not filas:
        return gpd.GeoDataFrame(
            columns=["id", "fecha", "provincia_effis", "municipio_effis", "area_ha_effis", "geometry"],
            geometry="geometry",
            crs="EPSG:4326",
        )
    datos = gpd.GeoDataFrame(filas, geometry="geometry", crs="EPSG:4326").to_crs(CRS_TRABAJO)
    datos["geometry"] = datos.geometry.simplify(40, preserve_topology=True)
    return datos


def agregar(perimetros: gpd.GeoDataFrame, municipios: gpd.GeoDataFrame, prefijo: str) -> pd.DataFrame:
    codigos = municipios[["codigo_ine"]].copy()
    if perimetros.empty:
        return pd.DataFrame(
            {
                "codigo_ine": codigos["codigo_ine"],
                f"n_incendios_{prefijo}": 0.0,
                f"ha_quemadas_{prefijo}": 0.0,
            }
        )
    base = municipios[["codigo_ine", "geometry"]].copy()
    base["geometry"] = base.geometry.simplify(40, preserve_topology=True)
    cruce = gpd.overlay(
        perimetros[["id", "geometry"]],
        base,
        how="intersection",
        keep_geom_type=False,
    )
    if cruce.empty:
        vacio = codigos.copy()
        vacio[f"n_incendios_{prefijo}"] = 0.0
        vacio[f"ha_quemadas_{prefijo}"] = 0.0
        return vacio
    cruce = cruce[cruce.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    cruce["ha"] = cruce.geometry.area / 10_000.0
    hectareas = cruce.groupby("codigo_ine", as_index=False)["ha"].sum()
    conteo = cruce.groupby("codigo_ine", as_index=False)["id"].nunique()
    hectareas = hectareas.rename(columns={"ha": f"ha_quemadas_{prefijo}"})
    conteo = conteo.rename(columns={"id": f"n_incendios_{prefijo}"})
    salida = codigos.merge(hectareas, on="codigo_ine", how="left").merge(conteo, on="codigo_ine", how="left")
    return salida


def _float(valor) -> float | None:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None
