"""Combustible a partir de Sentinel-1 RTC (Microsoft Planetary Computer).

No se descarga la escena entera (~1,8 GB a 10 m). Se lee una ventana COG
decimada a la resolución de trabajo, se pasa a dB y se hace la mediana
multitemporal sobre la rejilla EPSG:25830.
"""

from __future__ import annotations

import logging
import warnings
from datetime import datetime

import numpy as np
import planetary_computer
import pystac_client
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

from prioridad_galicia.config import (
    BBOX_LONLAT,
    CACHE,
    CRS_TRABAJO,
    S1_COLECCION,
    S1_FIN,
    S1_INICIO,
    STAC_PC,
)
from prioridad_galicia.geo import (
    cobertura_zonal,
    crear_rejilla,
    estadistica_zonal,
    rasterizar_zonas,
    reproyectar_a_rejilla,
)
from prioridad_galicia.sources.territorio import limites_trabajo

logger = logging.getLogger(__name__)


def calcular_sentinel1(municipios, max_escenas: int, resolucion_m: float, forzar: bool = False) -> tuple[object, dict]:
    encontradas = buscar_escenas(S1_INICIO, S1_FIN)
    seleccion = seleccionar_escenas(encontradas, max_escenas)
    alto, ancho, transform = crear_rejilla(limites_trabajo(municipios), resolucion_m)
    vh_capas = []
    ratio_capas = []
    usadas = []
    errores = []
    for item in seleccion:
        try:
            vh_db, vv_db, modo = escena_en_rejilla(
                item, transform, (alto, ancho), resolucion_m, forzar=forzar
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Escena %s descartada: %s", item.id, exc)
            errores.append({"id": item.id, "error": str(exc)})
            continue
        vh_capas.append(vh_db)
        ratio = vh_db - vv_db if vv_db is not None else np.full_like(vh_db, np.nan)
        ratio_capas.append(ratio)
        usadas.append(
            {
                "id": item.id,
                "fecha": item.datetime.isoformat() if item.datetime else None,
                "orbita": (item.properties or {}).get("sat:orbit_state"),
                "relativa": (item.properties or {}).get("sat:relative_orbit"),
                "modo_db": modo,
                "bbox": list(item.bbox) if item.bbox else None,
            }
        )
        logger.info("Sentinel-1 %s/%s incorporada (%s)", len(usadas), len(seleccion), item.id)

    salida = municipios[["codigo_ine"]].copy()
    meta = {
        "fuente": "Microsoft Planetary Computer, colección sentinel-1-rtc",
        "ventana": [S1_INICIO, S1_FIN],
        "escenas_encontradas": len(encontradas),
        "escenas_seleccionadas": [item.id for item in seleccion],
        "escenas_usadas": usadas,
        "errores": errores,
        "resolucion_m": resolucion_m,
        "ok": bool(vh_capas),
    }
    if not vh_capas:
        salida["vh_db"] = np.nan
        salida["ratio_vh_vv_db"] = np.nan
        salida["n_obs_sar"] = np.nan
        return salida, meta

    pila_vh = np.stack(vh_capas)
    pila_ratio = np.stack(ratio_capas)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="All-NaN slice encountered")
        vh_med = np.nanmedian(pila_vh, axis=0).astype(np.float32)
        ratio_med = np.nanmedian(pila_ratio, axis=0).astype(np.float32)
    cuentas = np.sum(np.isfinite(pila_vh), axis=0).astype(np.float32)
    zonas = rasterizar_zonas(municipios.geometry, alto, ancho, transform)
    n = len(municipios)
    salida["vh_db"] = estadistica_zonal(zonas, vh_med, n, "median")
    salida["ratio_vh_vv_db"] = estadistica_zonal(zonas, ratio_med, n, "median")
    salida["n_obs_sar"] = cobertura_zonal(zonas, cuentas, vh_med, n)
    return salida, meta


def buscar_escenas(inicio: str, fin: str) -> list:
    catalogo = pystac_client.Client.open(STAC_PC)
    busqueda = catalogo.search(
        collections=[S1_COLECCION],
        bbox=list(BBOX_LONLAT),
        datetime=f"{inicio}/{fin}",
    )
    escenas = []
    for item in busqueda.items():
        if "vh" not in item.assets or "vv" not in item.assets:
            continue
        modo = (item.properties or {}).get("sar:instrument_mode")
        if modo not in (None, "IW"):
            continue
        escenas.append(item)
    logger.info("STAC Sentinel-1 RTC: %s escenas con VH y VV", len(escenas))
    return escenas


def seleccionar_escenas(items: list, max_escenas: int) -> list:
    """Reparte pocas escenas en el verano y cubre este y oeste de Galicia."""
    candidatos = []
    for item in items:
        cobertura = fraccion_bbox(item.bbox, BBOX_LONLAT)
        if cobertura >= 0.08:
            candidatos.append((item, cobertura))
    if not candidatos:
        return []
    semanas: dict[str, list] = {}
    for item, cobertura in candidatos:
        fecha = item.datetime or datetime.fromisoformat("2024-07-01T00:00:00+00:00")
        clave = f"{fecha.isocalendar().year}-W{fecha.isocalendar().week:02d}"
        semanas.setdefault(clave, []).append((item, cobertura))
    seleccion = []
    for clave in _muestra(sorted(semanas), min(4, len(semanas))):
        grupo = sorted(semanas[clave], key=lambda par: par[1], reverse=True)
        seleccion.append(grupo[0][0])
        if len(seleccion) >= max_escenas:
            break
        if len(grupo) > 1 and len(seleccion) < max_escenas:
            lejos = max(grupo[1:], key=lambda par: separacion_bbox(grupo[0][0].bbox, par[0].bbox))
            seleccion.append(lejos[0])
    vistos = set()
    unicas = []
    for item in seleccion:
        if item.id in vistos:
            continue
        vistos.add(item.id)
        unicas.append(item)
    return unicas[:max_escenas]


def escena_en_rejilla(item, transform, forma, resolucion_m: float, forzar: bool = False):
    ruta = CACHE / "s1" / f"res{int(resolucion_m)}" / f"{_id_seguro(item.id)}.npz"
    firma = _firma_rejilla(transform, forma)
    if ruta.exists() and not forzar:
        with np.load(ruta) as cache:
            if cache["firma"].tobytes() == firma.tobytes():
                vh = np.array(cache["vh"])
                vv_bruto = np.array(cache["vv"]) if "vv" in cache.files else np.array([])
                vv = None if vv_bruto.size == 0 else vv_bruto
                modo = cache["modo"].item() if getattr(cache["modo"], "shape", ()) == () else str(cache["modo"])
                return vh, vv, str(modo)
    vh_lin, tr_vh, crs_vh, nodata_vh = leer_banda_decimada(
        item.assets["vh"].href, BBOX_LONLAT, resolucion_m
    )
    vh_db, modo = preparar_retrodispersion(vh_lin, nodata_vh)
    vh_grid = reproyectar_a_rejilla(vh_db, tr_vh, crs_vh, transform, forma, CRS_TRABAJO)
    vv_grid = None
    try:
        vv_lin, tr_vv, crs_vv, nodata_vv = leer_banda_decimada(
            item.assets["vv"].href, BBOX_LONLAT, resolucion_m
        )
        vv_db, _ = preparar_retrodispersion(vv_lin, nodata_vv)
        vv_grid = reproyectar_a_rejilla(vv_db, tr_vv, crs_vv, transform, forma, CRS_TRABAJO)
    except Exception as exc:  # noqa: BLE001
        logger.warning("VV no leída en %s: %s", item.id, exc)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        ruta,
        vh=vh_grid,
        vv=vv_grid if vv_grid is not None else np.array([]),
        modo=np.array(modo),
        firma=firma,
    )
    return vh_grid, vv_grid, modo


def pixel_metros(transform, crs) -> float:
    """Lado del píxel en metros, también si el CRS es geográfico."""
    dx = abs(float(transform.a)) or 10.0
    if crs is not None and getattr(crs, "is_geographic", False):
        return dx * 111_320.0
    return dx


def leer_banda_decimada(href: str, limites_lonlat, resolucion_m: float):
    """Lee el cruce de la escena con Galicia usando el overview del COG."""
    firmada = planetary_computer.sign(href)
    oeste, sur, este, norte = limites_lonlat
    with _entorno_gdal():
        with rasterio.open(firmada) as src:
            izquierda, abajo, derecha, arriba = transform_bounds(
                "EPSG:4326", src.crs, oeste, sur, este, norte, densify_pts=21
            )
            ventana = from_bounds(izquierda, abajo, derecha, arriba, transform=src.transform)
            ventana = ventana.intersection(Window(0, 0, src.width, src.height))
            if ventana.width < 2 or ventana.height < 2:
                raise RuntimeError("la escena no intersecta Galicia")
            factor = max(1, int(round(resolucion_m / pixel_metros(src.transform, src.crs))))
            alto = max(1, int(np.ceil(ventana.height / factor)))
            ancho = max(1, int(np.ceil(ventana.width / factor)))
            datos = src.read(
                1,
                window=ventana,
                out_shape=(alto, ancho),
                resampling=Resampling.average,
            ).astype(np.float32)
            transform_ventana = src.window_transform(ventana)
            transform_salida = transform_ventana * Affine.scale(ventana.width / ancho, ventana.height / alto)
            return datos, transform_salida, src.crs, src.nodata


def preparar_retrodispersion(array: np.ndarray, nodata) -> tuple[np.ndarray, str]:
    """Enmascara el nodata y convierte gamma0 lineal a dB si hace falta.

    El RTC de Planetary Computer está en potencia (lineal). Si la mediana de
    los valores plausibles ya es negativa, el array venía en dB y no se toca.
    """
    datos = array.astype(np.float32, copy=True)
    if nodata is not None and np.isfinite(nodata):
        datos[np.isclose(datos, float(nodata))] = np.nan
    datos[datos <= -100] = np.nan
    validos = datos[np.isfinite(datos)]
    if validos.size == 0:
        return datos, "vacio"
    mediana = float(np.median(validos))
    if mediana < 0:
        return datos, "ya_db"
    decibelios = np.full(datos.shape, np.nan, dtype=np.float32)
    mascara = np.isfinite(datos) & (datos > 0)
    decibelios[mascara] = 10.0 * np.log10(datos[mascara])
    return decibelios, "lineal_a_db"


def fraccion_bbox(bbox, ambito) -> float:
    if not bbox or len(bbox) != 4:
        return 0.0
    oeste, sur, este, norte = ambito
    ancho = max(0.0, min(bbox[2], este) - max(bbox[0], oeste))
    alto = max(0.0, min(bbox[3], norte) - max(bbox[1], sur))
    area = (este - oeste) * (norte - sur)
    return 0.0 if area <= 0 else (ancho * alto) / area


def separacion_bbox(a, b) -> float:
    if not a or not b:
        return 0.0
    centro_a = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2)
    centro_b = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    return (centro_a[0] - centro_b[0]) ** 2 + (centro_a[1] - centro_b[1]) ** 2


def _muestra(valores: list, k: int) -> list:
    if k <= 0 or not valores:
        return []
    if len(valores) <= k:
        return list(valores)
    indices = [round(i * (len(valores) - 1) / (k - 1)) for i in range(k)]
    salida = []
    for indice in indices:
        if valores[indice] not in salida:
            salida.append(valores[indice])
    return salida


def _firma_rejilla(transform, forma) -> np.ndarray:
    return np.array(
        [forma[0], forma[1], transform.a, transform.e, transform.c, transform.f],
        dtype=np.float64,
    )


def _id_seguro(identificador: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in identificador)


def _entorno_gdal():
    return rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff,.TIF",
        GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
        GDAL_HTTP_MULTIPLEX="YES",
        GDAL_HTTP_VERSION="2",
        VSI_CACHE="TRUE",
        VSI_CACHE_SIZE=200_000_000,
        GDAL_HTTP_TIMEOUT=120,
        GDAL_HTTP_MAX_RETRY=3,
        GDAL_HTTP_RETRY_DELAY=2,
        CPL_VSIL_CURL_USE_HEAD="NO",
    )
