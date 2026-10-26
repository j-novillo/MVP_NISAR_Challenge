"""Orquesta las fases. Una fuente caída deja el hueco y el resto sigue."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import geopandas as gpd
import pandas as pd

from prioridad_galicia.config import (
    CACHE,
    PRESETS,
    PROCESSED,
    SALIDA_CSV,
    SALIDA_FIGURA,
    SALIDA_GEOJSON,
    SALIDA_GPKG,
    SALIDA_MANIFIESTO,
    SALIDA_NISAR_ZONAL,
    SALIDA_VALIDACION,
)
from prioridad_galicia.index import calcular_prioridad, construir_componentes
from prioridad_galicia.sources.fwi import anadir_fwi
from prioridad_galicia.sources.incendios import anadir_incendios
from prioridad_galicia.sources.nisar import buscar_nisar, procesar_nisar
from prioridad_galicia.sources.osm import anadir_accesibilidad
from prioridad_galicia.sources.poblacion import anadir_poblacion
from prioridad_galicia.sources.sentinel1 import calcular_sentinel1
from prioridad_galicia.sources.territorio import cargar_municipios
from prioridad_galicia.sources.worldcover import anadir_worldcover
from prioridad_galicia.validation import evaluar, figura_quintiles

logger = logging.getLogger(__name__)

COMANDO_NISAR = (
    "EARTHDATA_TOKEN=tu_token python -m prioridad_galicia.cli nisar-procesar --max-escenas 2"
)


def ejecutar_pipeline(max_escenas_s1: int = 8, resolucion: float = 400, forzar: bool = False) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    manifiesto: dict = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "crs": "EPSG:25830",
        "ambito": "Galicia (municipios)",
        "fases": {},
        "comando_nisar": COMANDO_NISAR,
    }
    municipios = cargar_municipios(forzar=forzar)
    manifiesto["fases"]["territorio"] = {
        "ok": True,
        "municipios": int(len(municipios)),
        "fuente": "IGN WFS unidades administrativas, nivel municipal, filtrado a Galicia",
    }

    municipios, meta_pob = _fase("poblacion", lambda: anadir_poblacion(municipios), manifiesto, municipios)
    municipios, meta_fuegos = _fase("incendios", lambda: anadir_incendios(municipios), manifiesto, municipios)
    municipios, meta_fwi = _fase("fwi", lambda: anadir_fwi(municipios), manifiesto, municipios)
    municipios, meta_osm = _fase("osm", lambda: anadir_accesibilidad(municipios), manifiesto, municipios)
    municipios, meta_wc = _fase("worldcover", lambda: anadir_worldcover(municipios), manifiesto, municipios)

    def _sar():
        columnas, meta = calcular_sentinel1(
            municipios, max_escenas=max_escenas_s1, resolucion_m=resolucion, forzar=forzar
        )
        unido = municipios.drop(columns=[c for c in ("vh_db", "ratio_vh_vv_db", "n_obs_sar") if c in municipios], errors="ignore")
        unido = unido.merge(columnas, on="codigo_ine", how="left")
        return unido, meta

    municipios, meta_s1 = _fase("sentinel1", _sar, manifiesto, municipios)

    try:
        catalogo = buscar_nisar()
        manifiesto["fases"]["nisar_busqueda"] = {
            "ok": True,
            "n_escenas": catalogo["n_escenas"],
            "colecciones": catalogo["colecciones"],
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("La búsqueda NISAR falló")
        manifiesto["fases"]["nisar_busqueda"] = {"ok": False, "error": str(exc)}
        catalogo = None

    token = os.environ.get("EARTHDATA_TOKEN", "").strip()
    if token:
        try:
            zonal = procesar_nisar(municipios, max_escenas=2, resolucion_m=200)
            municipios = _unir_nisar(municipios, zonal)
            manifiesto["fases"]["nisar_procesado"] = {"ok": True, "escenas": 2}
        except Exception as exc:  # noqa: BLE001
            logger.exception("NISAR no se procesó; el índice queda en Sentinel-1")
            manifiesto["fases"]["nisar_procesado"] = {"ok": False, "error": str(exc)}
    else:
        manifiesto["fases"]["nisar_procesado"] = {
            "ok": False,
            "motivo": "sin EARTHDATA_TOKEN en el entorno",
            "comando": COMANDO_NISAR,
        }
        if SALIDA_NISAR_ZONAL.exists():
            zonal = pd.read_csv(SALIDA_NISAR_ZONAL, dtype={"codigo_ine": str})
            municipios = _unir_nisar(municipios, zonal)
            manifiesto["fases"]["nisar_procesado"]["zonal_previo"] = str(SALIDA_NISAR_ZONAL)

    for columna in ("vh_db", "ratio_vh_vv_db", "n_obs_sar", "fwi_medio", "poblacion", "dist_parque_km", "densidad_viaria", "frac_forestal"):
        if columna not in municipios:
            municipios[columna] = pd.NA
    for columna in ("n_incendios_hist", "ha_quemadas_hist", "ha_quemadas_1000ha_hist", "n_incendios_val", "ha_quemadas_val"):
        if columna not in municipios:
            municipios[columna] = pd.NA

    municipios = construir_componentes(municipios)
    municipios = calcular_prioridad(municipios, PRESETS["equilibrado"])
    municipios["fuente_combustible"] = _fuente_combustible(meta_s1, municipios)
    municipios["fuente_historial"] = (meta_fuegos or {}).get("fuente_historial") or "no-disponible"
    municipios["fuente_fwi"] = (meta_fwi or {}).get("fuente") or "no-disponible"
    municipios["fuente_poblacion"] = "INE padrón" if (meta_pob or {}).get("municipios_con_poblacion") else "no-disponible"
    municipios["fuente_accesibilidad"] = (
        "OSM Overpass" if (meta_osm or {}).get("parques") or (meta_osm or {}).get("tramos_viarios") else "no-disponible"
    )
    municipios["fuente_forestal"] = "ESA WorldCover 2021" if (meta_wc or {}).get("ok") else "no-disponible"

    if municipios["ha_quemadas_val"].notna().any():
        resumen = evaluar(municipios)
    else:
        resumen = {"error": "No hay hectáreas de validación: la fase EFFIS no produjo datos."}
    figura = figura_quintiles(resumen)
    figura.savefig(SALIDA_FIGURA, dpi=140)
    import matplotlib.pyplot as plt

    plt.close(figura)
    SALIDA_VALIDACION.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    _escribir(municipios)
    manifiesto["validacion"] = resumen
    manifiesto["cobertura"] = {
        componente: _cobertura(municipios, componente) for componente in ("comb", "hist", "fwi", "expo", "acces")
    }
    manifiesto["pesos_defecto"] = PRESETS["equilibrado"]
    manifiesto["nisar_en_indice"] = False
    manifiesto["nota_nisar"] = (
        "El índice por defecto usa Sentinel-1 del verano de 2024, anterior a la validación 2025-2026. "
        "Las escenas NISAR procesadas son del 13, 18 y 20 de octubre de 2026: posteriores a esa validación, "
        "así que vh_db_nisar no entra en COMB. El visor puede sustituirlo con el interruptor, apagado al abrir. "
        "La descarga usa Bearer directo: ASFSession.auth_with_token devuelve 403 porque la cuenta "
        "aún no ha aceptado la EULA de la aplicación de ASF."
    )
    SALIDA_MANIFIESTO.write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Salida: %s", SALIDA_GEOJSON)
    return manifiesto


def _fase(nombre: str, funcion, manifiesto: dict, anterior):
    try:
        resultado, meta = funcion()
        manifiesto["fases"][nombre] = {"ok": True, **_meta_json(meta)}
        return resultado, meta
    except Exception as exc:  # noqa: BLE001
        logger.exception("Fase %s falló", nombre)
        manifiesto["fases"][nombre] = {"ok": False, "error": str(exc)}
        return anterior, None


def _unir_nisar(municipios, zonal: pd.DataFrame):
    zonal = zonal.copy()
    zonal["codigo_ine"] = zonal["codigo_ine"].astype(str).str.zfill(5)
    columnas = [
        c
        for c in (
            "codigo_ine",
            "vh_db_nisar",
            "n_escenas_nisar",
            "cobertura_max_nisar",
            "escenas_nisar",
            "polarizacion_nisar",
        )
        if c in zonal.columns
    ]
    limpio = municipios.drop(columns=[c for c in columnas if c != "codigo_ine" and c in municipios.columns], errors="ignore")
    return limpio.merge(zonal[columnas], on="codigo_ine", how="left")


def _fuente_combustible(meta_s1, municipios) -> str:
    s1 = bool(meta_s1 and meta_s1.get("ok"))
    nisar = "vh_db_nisar" in municipios and municipios["vh_db_nisar"].notna().any()
    if s1 and nisar:
        return "sentinel-1-rtc (índice); nisar-l2-gcov disponible aparte, no entra en la validación"
    if s1:
        return "sentinel-1-rtc"
    if nisar:
        return "nisar-l2-gcov"
    return "no-disponible"


def _escribir(municipios) -> None:
    salida = municipios.copy()
    simplificada = salida.geometry.simplify(80, preserve_topology=True)
    usable = ~simplificada.is_empty & simplificada.notna()
    salida.loc[usable, "geometry"] = simplificada[usable]
    for columna in salida.columns:
        if columna in {"geometry", "codigo_ine", "nombre", "provincia", "factor_dominante"}:
            continue
        if columna.startswith("fuente_"):
            continue
        if pd.api.types.is_numeric_dtype(salida[columna]):
            decimales = 2 if columna in {"prioridad", "area_ha", "poblacion", "ha_quemadas_hist", "ha_quemadas_val"} else 4
            salida[columna] = pd.to_numeric(salida[columna], errors="coerce").round(decimales)
    salida["codigo_ine"] = salida["codigo_ine"].astype(str).str.zfill(5)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    salida.to_file(SALIDA_GPKG, driver="GPKG")
    geografico = salida.to_crs(4326)
    geografico.to_file(SALIDA_GEOJSON, driver="GeoJSON")
    geografico.drop(columns="geometry").to_csv(SALIDA_CSV, index=False)


def _cobertura(tabla, columna: str) -> float | None:
    if columna not in tabla:
        return None
    return round(float(tabla[columna].notna().mean()), 4)


def _meta_json(meta) -> dict:
    if not isinstance(meta, dict):
        return {"detalle": str(meta)}
    limpio = {}
    for clave, valor in meta.items():
        if clave == "escenas_usadas" and isinstance(valor, list) and len(valor) > 12:
            limpio[clave] = valor[:12]
            continue
        try:
            json.dumps(valor)
            limpio[clave] = valor
        except TypeError:
            limpio[clave] = str(valor)
    return limpio
