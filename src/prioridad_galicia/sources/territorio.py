"""Municipios de Galicia desde el WFS INSPIRE del IGN, en EPSG:25830."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
from shapely.validation import make_valid

from prioridad_galicia.config import (
    BBOX_WFS,
    CACHE,
    CRS_GEOGRAFICO,
    CRS_TRABAJO,
    PROVINCIAS,
    WFS_IGN,
)
from prioridad_galicia.http_client import obtener_json

logger = logging.getLogger(__name__)

CACHE_BRUTO = CACHE / "ign_unidades_galicia.geojson"
CACHE_MUNICIPIOS = CACHE / "municipios_25830.gpkg"


def cargar_municipios(forzar: bool = False) -> gpd.GeoDataFrame:
    CACHE.mkdir(parents=True, exist_ok=True)
    if CACHE_MUNICIPIOS.exists() and not forzar:
        logger.info("Municipios en caché: %s", CACHE_MUNICIPIOS)
        return gpd.read_file(CACHE_MUNICIPIOS)
    bruto = _descargar_bruto(forzar)
    municipios = _filtrar_municipios(bruto)
    municipios = municipios.to_crs(CRS_TRABAJO)
    municipios["geometry"] = municipios.geometry.map(_geometria_valida)
    municipios["area_ha"] = municipios.geometry.area / 10_000.0
    municipios = municipios[municipios["area_ha"] > 0].copy()
    municipios = municipios.sort_values("codigo_ine").reset_index(drop=True)
    municipios.to_file(CACHE_MUNICIPIOS, driver="GPKG")
    logger.info("Municipios IGN: %s", len(municipios))
    return municipios


def _descargar_bruto(forzar: bool) -> dict:
    if CACHE_BRUTO.exists() and not forzar:
        return json.loads(CACHE_BRUTO.read_text(encoding="utf-8"))
    features: list[dict] = []
    page = 100
    start = 0
    while start < 5000:
        url = (
            f"{WFS_IGN}?service=WFS&version=2.0.0&request=GetFeature"
            "&typeNames=au:AdministrativeUnit"
            "&outputFormat=application/geo%2Bjson"
            f"&count={page}&startIndex={start}"
            f"&srsName={CRS_GEOGRAFICO}"
            f"&bbox={BBOX_WFS},urn:ogc:def:crs:EPSG::4326"
        )
        pagina = obtener_json(url, timeout=180, intentos=3)
        lote = pagina.get("features") or []
        if not lote:
            break
        features.extend(lote)
        logger.info("WFS IGN: %s entidades acumuladas", len(features))
        if len(lote) < page:
            break
        start += page
    coleccion = {"type": "FeatureCollection", "features": features}
    CACHE_BRUTO.write_text(json.dumps(coleccion), encoding="utf-8")
    return coleccion


def _filtrar_municipios(coleccion: dict) -> gpd.GeoDataFrame:
    filas = []
    for feature in coleccion.get("features", []):
        props = feature.get("properties") or {}
        nivel = json.dumps(props.get("nationalLevel"), ensure_ascii=False)
        if "4thOrder" not in nivel:
            continue
        codigo_nacional = str(props.get("nationalCode") or "")
        if len(codigo_nacional) < 5 or not codigo_nacional[-5:].isdigit():
            continue
        codigo_ine = codigo_nacional[-5:]
        provincia = PROVINCIAS.get(codigo_ine[:2])
        if provincia is None:
            continue
        geometria = feature.get("geometry")
        if not geometria:
            continue
        filas.append(
            {
                "codigo_ine": codigo_ine,
                "nombre": _nombre(props.get("name")) or codigo_ine,
                "provincia": provincia,
                "codigo_nacional_ign": codigo_nacional,
                "geometry": shape(geometria),
            }
        )
    if not filas:
        raise RuntimeError("El WFS del IGN no devolvió municipios de Galicia.")
    datos = gpd.GeoDataFrame(filas, geometry="geometry", crs=CRS_GEOGRAFICO)
    # El área en grados solo sirve para desempatar duplicados; el área oficial va en 25830.
    datos["_area"] = datos.to_crs(CRS_TRABAJO).geometry.area
    datos = datos.sort_values("_area", ascending=False).drop_duplicates("codigo_ine", keep="first")
    return datos.drop(columns="_area").reset_index(drop=True)


def _nombre(objeto) -> str | None:
    textos: list[str] = []
    _recolectar_textos(objeto, textos)
    limpios = [texto.strip() for texto in textos if isinstance(texto, str) and texto.strip()]
    if not limpios:
        return None
    # El WFS puede repetir el endónimo. Nos quedamos con el primero, que es el oficial.
    return limpios[0]


def _recolectar_textos(objeto, acumulado: list[str]) -> None:
    if isinstance(objeto, dict):
        texto = objeto.get("text")
        if isinstance(texto, str):
            acumulado.append(texto)
        for valor in objeto.values():
            _recolectar_textos(valor, acumulado)
    elif isinstance(objeto, list):
        for valor in objeto:
            _recolectar_textos(valor, acumulado)


def _geometria_valida(geom):
    if geom is None or geom.is_empty:
        return geom
    if geom.is_valid:
        return geom
    return make_valid(geom)


def limites_trabajo(municipios: gpd.GeoDataFrame) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = municipios.total_bounds
    return (float(minx), float(miny), float(maxx), float(maxy))
