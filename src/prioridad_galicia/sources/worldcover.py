"""Fracción de bosque y matorral (ESA WorldCover 2021) por municipio.

Es una capa de contexto, no entra en el índice: el combustible del índice es
la retrodispersión SAR. Si Planetary Computer no responde, la columna queda vacía.
"""

from __future__ import annotations

import logging

import numpy as np
import planetary_computer
import pystac_client
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

from prioridad_galicia.config import BBOX_LONLAT, CRS_TRABAJO, STAC_PC
from prioridad_galicia.geo import crear_rejilla, fraccion_clases, rasterizar_zonas, reproyectar_clases
from prioridad_galicia.sources.sentinel1 import _entorno_gdal, pixel_metros
from prioridad_galicia.sources.territorio import limites_trabajo

logger = logging.getLogger(__name__)

CLASES_FORESTALES = {10, 20}
RESOLUCION_M = 200


def anadir_worldcover(municipios) -> tuple[object, dict]:
    salida = municipios.copy()
    salida["frac_forestal"] = np.nan
    meta = {"fuente": "ESA WorldCover 2021 v200 (Planetary Computer)", "teselas": [], "ok": False, "errores": []}
    try:
        teselas = _buscar_teselas()
    except Exception as exc:  # noqa: BLE001
        meta["errores"].append(str(exc))
        return salida, meta
    alto, ancho, transform = crear_rejilla(limites_trabajo(municipios), RESOLUCION_M)
    mosaico = np.zeros((alto, ancho), dtype=np.uint8)
    for item in teselas:
        try:
            clases, tr, crs = _leer_tesela(item.assets["map"].href)
            parcial = reproyectar_clases(clases, tr, crs, transform, (alto, ancho), CRS_TRABAJO)
        except Exception as exc:  # noqa: BLE001
            meta["errores"].append({"id": item.id, "error": str(exc)})
            logger.warning("WorldCover %s descartada: %s", item.id, exc)
            continue
        hueco = (mosaico == 0) & (parcial > 0)
        mosaico[hueco] = parcial[hueco]
        meta["teselas"].append(item.id)
    if not meta["teselas"]:
        return salida, meta
    zonas = rasterizar_zonas(municipios.geometry, alto, ancho, transform)
    salida["frac_forestal"] = fraccion_clases(zonas, mosaico, len(salida), CLASES_FORESTALES, nodata=0)
    meta["ok"] = True
    logger.info("WorldCover: fracción forestal en %s municipios", int(np.isfinite(salida["frac_forestal"]).sum()))
    return salida, meta


def _buscar_teselas():
    catalogo = pystac_client.Client.open(STAC_PC)
    busqueda = catalogo.search(collections=["esa-worldcover"], bbox=list(BBOX_LONLAT))
    return [item for item in busqueda.items() if "2021_v200" in item.id and "map" in item.assets]


def _leer_tesela(href: str):
    firmada = planetary_computer.sign(href)
    oeste, sur, este, norte = BBOX_LONLAT
    with _entorno_gdal():
        with rasterio.open(firmada) as src:
            izquierda, abajo, derecha, arriba = transform_bounds(
                "EPSG:4326", src.crs, oeste, sur, este, norte, densify_pts=21
            )
            ventana = from_bounds(izquierda, abajo, derecha, arriba, transform=src.transform)
            ventana = ventana.intersection(Window(0, 0, src.width, src.height))
            if ventana.width < 2 or ventana.height < 2:
                raise RuntimeError("la tesela no intersecta Galicia")
            factor = max(1, int(round(RESOLUCION_M / pixel_metros(src.transform, src.crs))))
            alto = max(1, int(np.ceil(ventana.height / factor)))
            ancho = max(1, int(np.ceil(ventana.width / factor)))
            datos = src.read(1, window=ventana, out_shape=(alto, ancho), resampling=Resampling.nearest)
            transform_ventana = src.window_transform(ventana)
            transform_salida = transform_ventana * Affine.scale(ventana.width / ancho, ventana.height / alto)
            return datos, transform_salida, src.crs
