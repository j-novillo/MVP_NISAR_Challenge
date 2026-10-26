"""FWI estacional de EFFIS (capa WMS ``mf010.fwi``) agregado por municipio.

Se pide un GeoTIFF georreferenciado de varias fechas del verano de 2024, antes
de la ventana de validación. Es peligro meteorológico, no área quemada.
"""

from __future__ import annotations

import logging
from io import BytesIO

import numpy as np
import rasterio
from rasterio.transform import from_bounds

from prioridad_galicia.config import (
    BBOX_ESTE,
    BBOX_NORTE,
    BBOX_OESTE,
    BBOX_SUR,
    CRS_TRABAJO,
    EFFIS_WMS,
    FWI_CAPA,
    FWI_FECHAS,
)
from prioridad_galicia.geo import crear_rejilla, estadistica_zonal, rasterizar_zonas, reproyectar_a_rejilla
from prioridad_galicia.http_client import obtener
from prioridad_galicia.sources.territorio import limites_trabajo

logger = logging.getLogger(__name__)

ANCHO = 265
ALTO = 210


def anadir_fwi(municipios, resolucion_m: float = 1000.0) -> tuple[object, dict]:
    alto, ancho, transform = crear_rejilla(limites_trabajo(municipios), resolucion_m)
    zonas = rasterizar_zonas(municipios.geometry, alto, ancho, transform)
    capas = []
    fechas_ok = []
    errores = []
    for fecha in FWI_FECHAS:
        try:
            array, transform_src, crs = descargar_fwi(fecha)
        except Exception as exc:  # noqa: BLE001
            errores.append({"fecha": fecha, "error": str(exc)})
            logger.warning("FWI %s no disponible: %s", fecha, exc)
            continue
        rejilla = reproyectar_a_rejilla(
            array,
            transform_src,
            crs,
            transform,
            (alto, ancho),
            CRS_TRABAJO,
        )
        capas.append(rejilla)
        fechas_ok.append(fecha)
    salida = municipios.copy()
    if not capas:
        salida["fwi_medio"] = np.nan
        meta = {"ok": False, "fechas": fechas_ok, "errores": errores, "fuente": None}
        return salida, meta
    media = np.nanmean(np.stack(capas), axis=0)
    salida["fwi_medio"] = estadistica_zonal(zonas, media, len(salida), estadistico="mean")
    meta = {
        "ok": True,
        "fuente": f"EFFIS WMS {FWI_CAPA}",
        "fechas": fechas_ok,
        "errores": errores,
        "resolucion_zonal_m": resolucion_m,
    }
    logger.info("FWI: %s fechas, media municipal calculada", len(fechas_ok))
    return salida, meta


def descargar_fwi(fecha: str):
    url = (
        f"{EFFIS_WMS}?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap"
        f"&LAYERS={FWI_CAPA}&STYLES=&FORMAT=image/tiff&SRS=EPSG:4326"
        f"&BBOX={BBOX_OESTE},{BBOX_SUR},{BBOX_ESTE},{BBOX_NORTE}"
        f"&WIDTH={ANCHO}&HEIGHT={ALTO}&TIME={fecha}"
    )
    respuesta = obtener(url, timeout=60, intentos=2)
    contenido = respuesta.content
    if contenido[:5] == b"<?xml" or contenido[:1] == b"<":
        raise RuntimeError(contenido[:240].decode("utf-8", "replace"))
    with rasterio.open(BytesIO(contenido)) as src:
        array = src.read(1).astype(np.float32)
        transform = src.transform
        crs = src.crs or "EPSG:4326"
        limites = src.bounds
    # Algunos GeoTIFF de WMS vienen sin georreferencia útil (origen en 0,0).
    if abs(limites.left) < 1 and abs(limites.bottom) < 1 and limites.right <= ANCHO + 1:
        transform = from_bounds(BBOX_OESTE, BBOX_SUR, BBOX_ESTE, BBOX_NORTE, ANCHO, ALTO)
        crs = "EPSG:4326"
    array[~np.isfinite(array)] = np.nan
    array[(array < 0) | (array > 200)] = np.nan
    return array, transform, crs
