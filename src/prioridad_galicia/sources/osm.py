"""Accesibilidad con OpenStreetMap vía Overpass.

- Distancia euclídea del punto interior del municipio al parque de bomberos
  (``amenity=fire_station``) más cercano.
- Densidad de vías principales (autovía, troncal, primaria y secundaria), en
  km por km².

No es un isocrono de red. Si Overpass no responde, las columnas quedan vacías.
"""

from __future__ import annotations

import json
import logging

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point

from prioridad_galicia.config import (
    BBOX_ESTE,
    BBOX_NORTE,
    BBOX_OESTE,
    BBOX_SUR,
    CACHE,
    CRS_TRABAJO,
    OVERPASS_SERVIDORES,
)
from prioridad_galicia.http_client import obtener_json

logger = logging.getLogger(__name__)

BBOX_OVERPASS = f"{BBOX_SUR},{BBOX_OESTE},{BBOX_NORTE},{BBOX_ESTE}"
VIAS = "motorway|trunk|primary|secondary"


def anadir_accesibilidad(municipios: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, dict]:
    salida = municipios.copy()
    meta: dict = {"fuente": "OpenStreetMap vía Overpass", "servidor": None, "errores": []}
    parques: dict = {"elements": []}
    vias: dict = {"elements": []}
    try:
        parques, servidor = consultar(_consulta_parques(), "parques")
        meta["servidor"] = servidor
    except Exception as exc:  # noqa: BLE001
        meta["errores"].append(f"parques: {exc}")
        logger.warning("Sin parques de bomberos OSM: %s", exc)
    try:
        vias, servidor = consultar(_consulta_vias(), "vias")
        meta["servidor"] = meta["servidor"] or servidor
    except Exception as exc:  # noqa: BLE001
        meta["errores"].append(f"vias: {exc}")
        logger.warning("Sin vías OSM: %s", exc)
    meta["parques"] = len(parques.get("elements", []))
    meta["tramos_viarios"] = len(vias.get("elements", []))
    salida["dist_parque_km"] = _distancia_parques(salida, parques)
    try:
        salida["densidad_viaria"] = _densidad_viaria(salida, vias)
    except Exception as exc:  # noqa: BLE001
        meta["errores"].append(f"densidad viaria: {exc}")
        salida["densidad_viaria"] = np.nan
        logger.warning("La densidad viaria no se pudo calcular: %s", exc)
    if meta["parques"] == 0:
        salida["dist_parque_km"] = np.nan
    if meta["tramos_viarios"] == 0:
        salida["densidad_viaria"] = np.nan
    return salida, meta


def consultar(consulta: str, etiqueta: str) -> tuple[dict, str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    ruta = CACHE / f"overpass_{etiqueta}.json"
    if ruta.exists():
        payload = json.loads(ruta.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "elements" in payload:
            logger.info("Overpass %s desde caché: %s elementos", etiqueta, len(payload["elements"]))
            return payload, "cache"
    ultimo = None
    for servidor in OVERPASS_SERVIDORES:
        try:
            payload = obtener_json(
                servidor,
                method="POST",
                data={"data": consulta},
                timeout=180,
                intentos=2,
            )
            if not isinstance(payload, dict) or "elements" not in payload:
                raise RuntimeError(f"respuesta inesperada de {servidor}")
            logger.info("Overpass %s: %s elementos (%s)", etiqueta, len(payload["elements"]), servidor)
            ruta.write_text(json.dumps(payload), encoding="utf-8")
            return payload, servidor
        except Exception as exc:  # noqa: BLE001
            ultimo = exc
            logger.warning("Overpass falló en %s: %s", servidor, exc)
    raise RuntimeError(f"Ningún servidor Overpass respondió ({etiqueta}): {ultimo}")


def _consulta_parques() -> str:
    return f"""
[out:json][timeout:90];
(
  node["amenity"="fire_station"]({BBOX_OVERPASS});
  way["amenity"="fire_station"]({BBOX_OVERPASS});
);
out center;
"""


def _consulta_vias() -> str:
    return f"""
[out:json][timeout:150];
(
  way["highway"~"^({VIAS})$"]({BBOX_OVERPASS});
);
out geom;
"""


def _distancia_parques(municipios: gpd.GeoDataFrame, payload: dict) -> pd.Series:
    puntos = []
    for elemento in payload.get("elements", []):
        if elemento.get("type") == "node" and "lat" in elemento:
            puntos.append(Point(elemento["lon"], elemento["lat"]))
        elif "center" in elemento:
            centro = elemento["center"]
            puntos.append(Point(centro["lon"], centro["lat"]))
    if not puntos:
        return pd.Series(np.nan, index=municipios.index)
    parques = gpd.GeoDataFrame(geometry=puntos, crs="EPSG:4326").to_crs(CRS_TRABAJO)
    coords = np.column_stack([parques.geometry.x, parques.geometry.y])
    arbol = cKDTree(coords)
    origen = municipios.geometry.representative_point()
    consulta = np.column_stack([origen.x, origen.y])
    distancias, _ = arbol.query(consulta, k=1)
    return pd.Series(distancias / 1000.0, index=municipios.index)


def _densidad_viaria(municipios: gpd.GeoDataFrame, payload: dict) -> pd.Series:
    lineas = []
    for elemento in payload.get("elements", []):
        geometria = elemento.get("geometry") or []
        coords = []
        for nodo in geometria:
            if isinstance(nodo, dict) and "lon" in nodo and "lat" in nodo:
                coords.append((float(nodo["lon"]), float(nodo["lat"])))
        if len(coords) >= 2:
            lineas.append(LineString(coords))
    if not lineas:
        return pd.Series(np.nan, index=municipios.index)
    vias = gpd.GeoDataFrame(geometry=lineas, crs="EPSG:4326").to_crs(CRS_TRABAJO)
    vias["geometry"] = vias.geometry.simplify(30, preserve_topology=True)
    base = municipios[["codigo_ine", "geometry", "area_ha"]].copy()
    # Por provincia: 30 000 ejes contra los 313 términos a la vez agota la memoria.
    trozos = []
    for _, bloque in base.groupby(municipios["provincia"]):
        trozo = gpd.overlay(vias, bloque[["codigo_ine", "geometry"]], how="intersection", keep_geom_type=False)
        if not trozo.empty:
            trozos.append(trozo)
    cruce = pd.concat(trozos, ignore_index=True) if trozos else vias.iloc[0:0]
    if cruce.empty:
        return pd.Series(0.0, index=municipios.index)
    cruce = cruce[cruce.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
    cruce["km"] = cruce.geometry.length / 1000.0
    suma = cruce.groupby("codigo_ine")["km"].sum()
    kilometros = municipios["codigo_ine"].map(suma).fillna(0.0)
    return pd.Series(kilometros.to_numpy() / (municipios["area_ha"].to_numpy() / 100.0), index=municipios.index)
