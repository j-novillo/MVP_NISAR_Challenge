"""NISAR L2 GCOV: catálogo público y procesado con token de Earthdata.

La búsqueda en CMR no pide cuenta. La descarga del HDF5 sí: lee
``EARTHDATA_TOKEN`` y pide el ``.h5`` con ``Authorization: Bearer``.
``ASFSession.auth_with_token`` no se usa: en esta cuenta devuelve 403
porque la EULA de la aplicación de ASF aún no está aceptada, y el Bearer
directo sobre ``url_h5`` sí descarga. Sin token, o si la lectura falla,
el índice sigue con Sentinel-1.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import Affine
from rasterio.crs import CRS

from prioridad_galicia.config import (
    BBOX_LONLAT,
    CACHE,
    CMR_GRANULES,
    CRS_TRABAJO,
    NISAR_COLECCIONES,
    POLARIZACIONES_CRUZADAS,
    POLARIZACIONES_POTENCIA,
    RAW,
    SALIDA_NISAR,
    SALIDA_NISAR_LECTURA,
    SALIDA_NISAR_ZONAL,
)
from prioridad_galicia.geo import crear_rejilla, estadistica_zonal, rasterizar_zonas, reproyectar_a_rejilla
from prioridad_galicia.http_client import obtener
from prioridad_galicia.sources.territorio import limites_trabajo

logger = logging.getLogger(__name__)

_POL_RE = re.compile(r"_([DHVQ]{4})_[A-Z]_\d{8}T")


def buscar_nisar(destino: Path | None = None) -> dict:
    """Lista las escenas GCOV cuyo recuadro toca Galicia. No descarga nada."""
    oeste, sur, este, norte = BBOX_LONLAT
    bbox = f"{oeste},{sur},{este},{norte}"
    escenas = []
    resumen = {}
    for coleccion in NISAR_COLECCIONES:
        entradas, aciertos = _paginar_cmr(coleccion, bbox)
        resumen[coleccion] = {"cmr_hits": aciertos, "granulos": len(entradas)}
        for entrada in entradas:
            escenas.append(_resumir_entrada(entrada, coleccion))
    escenas.sort(key=lambda fila: fila.get("inicio") or "")
    catalogo = {
        "ambito": "Galicia",
        "bbox_lonlat": list(BBOX_LONLAT),
        "colecciones": resumen,
        "n_escenas": len(escenas),
        "escenas": escenas,
        "nota": (
            "Catálogo público de CMR. El HDF5 se descarga solo con EARTHDATA_TOKEN "
            "mediante `python -m prioridad_galicia.cli nisar-procesar`."
        ),
    }
    ruta = destino or SALIDA_NISAR
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(_json(catalogo), encoding="utf-8")
    logger.info("NISAR: %s escenas GCOV sobre Galicia", len(escenas))
    return catalogo


# Fracción mínima de píxeles válidos de un municipio para aceptar una escena.
COBERTURA_MINIMA = 0.5


def procesar_nisar(municipios, max_escenas: int = 2, resolucion_m: float = 200, conservar: bool = False, escenas: list[str] | None = None) -> pd.DataFrame:
    """Descarga hasta ``max_escenas`` HDF5 y agrega HV (o HH) por municipio.

    Exige ``EARTHDATA_TOKEN``. Borra el HDF5 al terminar, salvo ``conservar``.
    """
    token = os.environ.get("EARTHDATA_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Falta EARTHDATA_TOKEN. Crea un token en https://urs.earthdata.nasa.gov/profile "
            "y ejecuta: EARTHDATA_TOKEN=... python -m prioridad_galicia.cli nisar-procesar --max-escenas 2"
        )
    catalogo = buscar_nisar()
    if escenas:
        elegidas = [e for e in catalogo["escenas"] if any(e["titulo"].startswith(t) for t in escenas)][:max_escenas]
    else:
        elegidas = _elegir(catalogo["escenas"], max_escenas)
    if not elegidas:
        raise RuntimeError("CMR no devolvió escenas NISAR GCOV sobre Galicia.")
    sesion = _sesion(token)
    alto, ancho, transform = crear_rejilla(limites_trabajo(municipios), resolucion_m)
    notas = []
    RAW.mkdir(parents=True, exist_ok=True)
    carpeta = RAW / "nisar"
    carpeta.mkdir(parents=True, exist_ok=True)
    zonas = rasterizar_zonas(municipios.geometry, alto, ancho, transform)
    n = len(municipios)
    pixeles_muni = np.bincount(zonas.ravel(), minlength=n + 1)[1:].astype(float)
    medianas, fracciones = [], []
    for escena in elegidas:
        ruta = _descargar(escena, carpeta, sesion)
        try:
            array, tr, crs, info = leer_gcov(ruta, resolucion_objetivo_m=resolucion_m)
            array = filtro_mediana(array, size=3)
            rejilla = reproyectar_a_rejilla(array, tr, crs, transform, (alto, ancho), CRS_TRABAJO)
            # Combinación por municipio: mediana zonal de cada escena por separado
            # y fracción de píxeles del municipio con dato válido en esa escena.
            validos = np.bincount(zonas[np.isfinite(rejilla)], minlength=n + 1)[1:]
            fracciones.append(np.divide(validos, pixeles_muni, out=np.zeros(n), where=pixeles_muni > 0))
            medianas.append(estadistica_zonal(zonas, rejilla, n, "median"))
            notas.append({"id": escena["id"], "titulo": escena["titulo"], "inicio": escena.get("inicio"),
                          "municipios_cubiertos_50": int((fracciones[-1] >= COBERTURA_MINIMA).sum()), **info})
        finally:
            if ruta.exists() and not conservar:
                ruta.unlink()
    if not medianas:
        raise RuntimeError("No se pudo leer ninguna escena NISAR descargada.")
    M = np.vstack(medianas)
    F = np.vstack(fracciones)
    usar = F >= COBERTURA_MINIMA  # solo escenas que cubren >= umbral del municipio
    M_ok = np.where(usar, M, np.nan)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        valor = np.nanmedian(M_ok, axis=0)  # mediana entre escenas válidas
    zonal = municipios[["codigo_ine"]].copy()
    zonal["vh_db_nisar"] = valor
    zonal["n_escenas_nisar"] = usar.sum(axis=0)
    zonal["cobertura_max_nisar"] = np.round(F.max(axis=0), 3)
    zonal["escenas_nisar"] = [";".join(notas[i]["id"] for i in np.flatnonzero(usar[:, j])) for j in range(n)]
    zonal["polarizacion_nisar"] = notas[-1].get("polarizacion")
    CACHE.mkdir(parents=True, exist_ok=True)
    lectura = _json(
        {
            "escenas": notas,
            "cobertura_minima": COBERTURA_MINIMA,
            "combinacion": "mediana zonal por escena; mediana entre escenas con cobertura >= umbral",
        }
    )
    (CACHE / "nisar_lectura.json").write_text(lectura, encoding="utf-8")
    SALIDA_NISAR_LECTURA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA_NISAR_LECTURA.write_text(lectura, encoding="utf-8")
    SALIDA_NISAR_ZONAL.parent.mkdir(parents=True, exist_ok=True)
    zonal.to_csv(SALIDA_NISAR_ZONAL, index=False)
    logger.info("NISAR zonal escrito en %s", SALIDA_NISAR_ZONAL)
    return zonal


def leer_gcov(ruta: Path, resolucion_objetivo_m: float = 200) -> tuple[np.ndarray, Affine, CRS, dict]:
    """Lee la potencia cruzada (HVHV) de un GCOV, en dB, submuestreada.

    Recorre el HDF5 y se queda con el primer dataset 2D cuyo nombre es una
    polarización de potencia. Prefiere ``frequencyA`` (banda L) y HVHV.
    """
    with h5py.File(ruta, "r") as hdf:
        candidatos = _dataset_polarizacion(hdf)
        if not candidatos:
            raise RuntimeError(f"No hay capas de potencia (HHHH/HVHV/VVVV) en {ruta.name}")
        elegido = _preferir(candidatos)
        dataset = hdf[elegido]
        grupo = dataset.parent
        xs, ys = _coordenadas(grupo)
        array = np.array(dataset)
        if array.ndim != 2:
            raise RuntimeError(f"{elegido} no es una retícula 2D")
        if array.shape == (xs.size, ys.size):
            array = array.T
        elif array.shape != (ys.size, xs.size):
            raise RuntimeError(
                f"Forma {array.shape} incompatible con x={xs.size} y={ys.size} en {elegido}"
            )
        paso = float(np.median(np.abs(np.diff(xs)))) if xs.size > 1 else resolucion_objetivo_m
        stride = max(1, int(round(resolucion_objetivo_m / paso))) if paso > 0 else 1
        array = array[::stride, ::stride].astype(np.float32)
        xs = xs[::stride]
        ys = ys[::stride]
        epsg = _buscar_epsg(grupo) or _buscar_epsg(hdf)
        if epsg is None:
            raise RuntimeError(
                "El GCOV no declara EPSG en atributos. No se asigna un CRS por defecto."
            )
        transform = _transform_desde_ejes(xs, ys)
        decibelios, modo = _a_db(array)
        info = {
            "dataset": elegido,
            "polarizacion": elegido.split("/")[-1],
            "epsg": int(epsg),
            "stride": stride,
            "paso_m": paso,
            "modo_db": modo,
            "frecuencia": "L" if "frequencyA" in elegido else ("S" if "frequencyB" in elegido else "desconocida"),
        }
        return decibelios, transform, CRS.from_epsg(int(epsg)), info


def filtro_mediana(array: np.ndarray, size: int = 3) -> np.ndarray:
    """Mediana espacial size×size que ignora NaN. El GCOV ya viene multilooked."""
    if size < 2:
        return array
    radio = size // 2
    relleno = np.pad(array.astype(np.float32), radio, constant_values=np.nan)
    vistas = [
        relleno[y : y + array.shape[0], x : x + array.shape[1]]
        for y in range(size)
        for x in range(size)
    ]
    return np.nanmedian(np.stack(vistas), axis=0).astype(np.float32)


def gamma0_a_db(lineal: np.ndarray) -> np.ndarray:
    """10·log10 de la potencia. Los valores no positivos pasan a NaN."""
    salida = np.full(lineal.shape, np.nan, dtype=np.float32)
    mascara = np.isfinite(lineal) & (lineal > 0)
    salida[mascara] = 10.0 * np.log10(lineal[mascara].astype(np.float64))
    return salida


def _a_db(array: np.ndarray) -> tuple[np.ndarray, str]:
    validos = array[np.isfinite(array) & (array > -100)]
    if validos.size == 0:
        return array.astype(np.float32), "vacio"
    if float(np.median(validos)) < 0:
        datos = array.astype(np.float32, copy=True)
        datos[datos <= -100] = np.nan
        return datos, "ya_db"
    datos = gamma0_a_db(array).astype(np.float32)
    # Píxeles a 0/casi 0 (relleno en bordes de escena) dan ~-140 dB: se anulan.
    datos[datos < -50] = np.nan
    return datos, "lineal_a_db"


def _dataset_polarizacion(hdf: h5py.File) -> list[str]:
    encontrados = []

    def visitar(nombre, obj):
        if isinstance(obj, h5py.Dataset) and obj.ndim == 2:
            base = nombre.split("/")[-1].upper()
            if base in POLARIZACIONES_POTENCIA or base in POLARIZACIONES_CRUZADAS:
                encontrados.append(nombre)

    hdf.visititems(visitar)
    return encontrados


def _preferir(rutas: list[str]) -> str:
    def puntuacion(ruta: str) -> tuple:
        base = ruta.split("/")[-1].upper()
        cruzada = 0 if base in POLARIZACIONES_CRUZADAS else 1
        banda_l = 0 if "frequencyA" in ruta else 1
        orden = {"HVHV": 0, "HHHV": 1, "VVVH": 2, "HHHH": 3, "VVVV": 4}.get(base, 9)
        return (cruzada, banda_l, orden, ruta)

    return sorted(rutas, key=puntuacion)[0]


def _coordenadas(grupo: h5py.Group) -> tuple[np.ndarray, np.ndarray]:
    nombres = {clave.lower(): clave for clave in grupo.keys()}
    x_clave = nombres.get("xcoordinates") or nombres.get("x_coordinates") or nombres.get("x")
    y_clave = nombres.get("ycoordinates") or nombres.get("y_coordinates") or nombres.get("y")
    if x_clave is None or y_clave is None:
        raise RuntimeError(f"El grupo {grupo.name} no tiene ejes x/y. Claves: {list(grupo.keys())[:12]}")
    return np.array(grupo[x_clave]).astype(float), np.array(grupo[y_clave]).astype(float)


def _transform_desde_ejes(xs: np.ndarray, ys: np.ndarray) -> Affine:
    dx = float((xs[-1] - xs[0]) / (xs.size - 1)) if xs.size > 1 else 1.0
    dy = float((ys[-1] - ys[0]) / (ys.size - 1)) if ys.size > 1 else -1.0
    return Affine(dx, 0.0, float(xs[0] - dx / 2), 0.0, dy, float(ys[0] - dy / 2))


def _buscar_epsg(obj) -> int | None:
    cola = [obj]
    vistos = 0
    while cola and vistos < 30:
        actual = cola.pop(0)
        vistos += 1
        atributos = getattr(actual, "attrs", {})
        for clave, valor in atributos.items():
            if "epsg" in str(clave).lower():
                try:
                    return int(np.array(valor).reshape(-1)[0])
                except (TypeError, ValueError):
                    continue
        if isinstance(actual, h5py.Group):
            for clave in ("projection", "crs", "spatial_ref"):
                if clave in actual and isinstance(actual[clave], h5py.Dataset):
                    ds = actual[clave]
                    # NISAR GCOV: dataset escalar con el EPSG y atributo epsg_code.
                    if "epsg_code" in ds.attrs:
                        return int(np.array(ds.attrs["epsg_code"]).reshape(-1)[0])
                    if np.issubdtype(ds.dtype, np.integer) and ds.size == 1:
                        return int(np.array(ds[()]).reshape(-1)[0])
                    crudo = ds[()]
                    texto = crudo.decode() if isinstance(crudo, bytes) else str(crudo)
                    if "EPSG" in texto.upper():
                        coincidencia = re.search(r"EPSG[\"']?[,:](\d+)", texto.upper())
                        if coincidencia:
                            return int(coincidencia.group(1))
            # Solo un nivel hacia arriba: el CRS suele estar en el grupo de la retícula.
            if actual is obj and actual.parent is not None and actual.parent.name not in ("/", ""):
                cola.append(actual.parent)
    return None


def _paginar_cmr(coleccion: str, bbox: str) -> tuple[list, int | None]:
    entradas = []
    aciertos = None
    pagina = 1
    while pagina <= 20:
        respuesta = obtener(
            CMR_GRANULES,
            params={
                "short_name": coleccion,
                "bounding_box": bbox,
                "page_size": 200,
                "page_num": pagina,
            },
            headers={"Accept": "application/json"},
            timeout=90,
        )
        if aciertos is None and respuesta.headers.get("CMR-Hits"):
            aciertos = int(respuesta.headers["CMR-Hits"])
        lote = respuesta.json().get("feed", {}).get("entry") or []
        if isinstance(lote, dict):
            lote = [lote]
        if not lote:
            break
        entradas.extend(lote)
        if len(lote) < 200:
            break
        pagina += 1
    return entradas, aciertos


def _resumir_entrada(entrada: dict, coleccion: str) -> dict:
    titulo = entrada.get("title") or entrada.get("producer_granule_id")
    enlaces = []
    for enlace in entrada.get("links") or []:
        href = enlace.get("href") or ""
        if href.endswith(".h5") and "PRIVATE" not in href and href.startswith("https"):
            enlaces.append(href)
    pol = _POL_RE.search(titulo or "")
    return {
        "id": entrada.get("id"),
        "titulo": titulo,
        "coleccion": coleccion,
        "inicio": entrada.get("time_start"),
        "fin": entrada.get("time_end"),
        "tamano_mb": _float(entrada.get("granule_size")),
        "modo_polarimetrico": pol.group(1) if pol else None,
        "url_h5": enlaces[0] if enlaces else None,
        "dataset_id": entrada.get("dataset_id"),
    }


def _elegir(escenas: list[dict], max_escenas: int) -> list[dict]:
    """Prioriza la colección provisional y los modos con polarización cruzada."""
    def orden(escena: dict) -> tuple:
        provisional = 0 if "PROVISIONAL" in escena["coleccion"] else 1
        cruzada = 0 if escena.get("modo_polarimetrico") and "V" in escena["modo_polarimetrico"] else 1
        # Las más recientes primero (antes cogía las más antiguas).
        return (provisional, cruzada, -_ts(escena.get("inicio")))

    con_url = [escena for escena in escenas if escena.get("titulo")]
    return sorted(con_url, key=orden)[:max_escenas]


def _ts(valor) -> float:
    try:
        return pd.Timestamp(valor).timestamp()
    except Exception:
        return 0.0


def _descargar(escena: dict, carpeta: Path, sesion) -> Path:
    """Descarga directa del HDF5 por url_h5 con cabecera Bearer.

    asf_search.auth_with_token falla (403 "EULA Acceptance Failure") si la
    cuenta no ha autorizado la app de ASF, aunque el token sea válido para
    descargar. La descarga directa funciona igualmente.
    """
    url = escena.get("url_h5")
    if url:
        destino = carpeta / url.rsplit("/", 1)[-1]
        if not destino.exists():
            parcial = destino.with_suffix(".part")
            with sesion.get(url, stream=True, timeout=600) as r:
                r.raise_for_status()
                with open(parcial, "wb") as f:
                    for trozo in r.iter_content(8 << 20):
                        f.write(trozo)
            parcial.rename(destino)
        return destino
    import asf_search as asf

    nombre = escena["titulo"]
    resultados = asf.granule_search([nombre], session=sesion)
    if len(resultados) == 0:
        raise RuntimeError(f"ASF no encontró el gránulo {nombre}")
    resultados.download(path=str(carpeta), session=sesion, processes=1)
    candidatos = list(carpeta.glob(f"{nombre}*.h5")) + list(carpeta.glob("*.h5"))
    if not candidatos:
        raise RuntimeError(f"La descarga de {nombre} no dejó un HDF5 en {carpeta}")
    # El producto científico, no el QA_STATS.
    ciencia = [ruta for ruta in candidatos if ruta.name.startswith(nombre) and "QA" not in ruta.name]
    return ciencia[0] if ciencia else candidatos[0]


def _sesion(token: str):
    import requests

    # Sesión con Bearer; requests conserva la cabecera en las redirecciones
    # dentro de earthdatacloud y la quita al saltar a CloudFront (URL firmada).
    sesion = requests.Session()
    sesion.headers["Authorization"] = f"Bearer {token}"
    return sesion


def _json(objeto) -> str:
    import json

    return json.dumps(objeto, ensure_ascii=False, indent=2)


def _float(valor):
    try:
        return round(float(valor), 1)
    except (TypeError, ValueError):
        return None
