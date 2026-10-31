"""Rejilla de trabajo y estadísticas zonales por municipio."""

from __future__ import annotations

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import Affine, from_origin
from rasterio.warp import Resampling, reproject


def crear_rejilla(limites: tuple[float, float, float, float], resolucion_m: float) -> tuple[int, int, Affine]:
    """Devuelve (alto, ancho, transform) alineada a ``resolucion_m`` en metros."""
    minx, miny, maxx, maxy = limites
    minx = np.floor(minx / resolucion_m) * resolucion_m
    miny = np.floor(miny / resolucion_m) * resolucion_m
    maxx = np.ceil(maxx / resolucion_m) * resolucion_m
    maxy = np.ceil(maxy / resolucion_m) * resolucion_m
    ancho = max(1, int(round((maxx - minx) / resolucion_m)))
    alto = max(1, int(round((maxy - miny) / resolucion_m)))
    transform = from_origin(minx, maxy, resolucion_m, resolucion_m)
    return alto, ancho, transform


def rasterizar_zonas(geometrias, alto: int, ancho: int, transform: Affine) -> np.ndarray:
    """Identificadores 1..N. El 0 es fuera de municipio."""
    formas = [(geom, indice + 1) for indice, geom in enumerate(geometrias) if geom is not None and not geom.is_empty]
    if not formas:
        return np.zeros((alto, ancho), dtype=np.int32)
    return rasterize(
        formas,
        out_shape=(alto, ancho),
        transform=transform,
        fill=0,
        dtype=np.int32,
        all_touched=True,
    )


def estadistica_zonal(zonas: np.ndarray, valores: np.ndarray, n_zonas: int, estadistico: str = "median") -> np.ndarray:
    """Mediana o media de los píxeles finitos de cada zona. NaN si no hay píxeles."""
    salida = np.full(n_zonas, np.nan, dtype=np.float64)
    funcion = np.nanmedian if estadistico == "median" else np.nanmean
    finitos = np.isfinite(valores)
    for zona in range(1, n_zonas + 1):
        mascara = (zonas == zona) & finitos
        if not mascara.any():
            continue
        salida[zona - 1] = float(funcion(valores[mascara]))
    return salida


def cobertura_zonal(zonas: np.ndarray, cuentas: np.ndarray, valores: np.ndarray, n_zonas: int) -> np.ndarray:
    """Mediana del número de observaciones SAR en los píxeles válidos de la zona."""
    salida = np.full(n_zonas, np.nan, dtype=np.float64)
    finitos = np.isfinite(valores)
    for zona in range(1, n_zonas + 1):
        mascara = (zonas == zona) & finitos
        if not mascara.any():
            continue
        salida[zona - 1] = float(np.median(cuentas[mascara]))
    return salida


def fraccion_clases(
    zonas: np.ndarray,
    clases: np.ndarray,
    n_zonas: int,
    positivas: set[int],
    nodata: int = 0,
) -> np.ndarray:
    """Fracción de píxeles válidos cuya clase está en ``positivas``."""
    salida = np.full(n_zonas, np.nan, dtype=np.float64)
    for zona in range(1, n_zonas + 1):
        mascara = zonas == zona
        if not mascara.any():
            continue
        validos = mascara & (clases != nodata)
        if not validos.any():
            continue
        salida[zona - 1] = float(np.isin(clases[validos], list(positivas)).mean())
    return salida


def reproyectar_a_rejilla(
    origen: np.ndarray,
    transform_origen,
    crs_origen,
    transform_destino,
    forma_destino: tuple[int, int],
    crs_destino,
    resampling: Resampling = Resampling.average,
    nodata_origen: float = np.nan,
) -> np.ndarray:
    """Reproyecta un array a la rejilla municipal. El destino arranca en NaN."""
    destino = np.full(forma_destino, np.nan, dtype=np.float32)
    reproject(
        source=origen.astype(np.float32),
        destination=destino,
        src_transform=transform_origen,
        src_crs=crs_origen,
        src_nodata=nodata_origen,
        dst_transform=transform_destino,
        dst_crs=crs_destino,
        dst_nodata=np.nan,
        resampling=resampling,
    )
    return destino


def reproyectar_clases(
    origen: np.ndarray,
    transform_origen,
    crs_origen,
    transform_destino,
    forma_destino: tuple[int, int],
    crs_destino,
) -> np.ndarray:
    """Vecino más próximo, para no inventar clases intermedias."""
    destino = np.zeros(forma_destino, dtype=np.uint8)
    reproject(
        source=origen.astype(np.uint8),
        destination=destino,
        src_transform=transform_origen,
        src_crs=crs_origen,
        src_nodata=0,
        dst_transform=transform_destino,
        dst_crs=crs_destino,
        dst_nodata=0,
        resampling=Resampling.nearest,
    )
    return destino
