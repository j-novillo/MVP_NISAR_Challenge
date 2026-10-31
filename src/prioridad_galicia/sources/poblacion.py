"""Padrón municipal del INE (tablas provinciales, último año publicado).

La API no trae el código INE en el nombre de la serie. Se cruza por topónimo
dentro de la provincia. El mayor valor de cada tabla es el total provincial
(la suma de los concellos) y se descarta: no es un municipio.
"""

from __future__ import annotations

import logging
import re
import unicodedata

import numpy as np
import pandas as pd

from prioridad_galicia.config import INE_DATOS, PROVINCIAS, TABLAS_INE_POBLACION
from prioridad_galicia.http_client import obtener_json

logger = logging.getLogger(__name__)

ARTICULOS = {"a", "o", "as", "os", "el", "la", "los", "las"}

# El IGN conserva el topónimo tradicional y el padrón el nombre oficial vigente.
# Comprobado contra el código INE de la geometría: 27002 Alfoz, 32023 Castro
# Caldelas, 36008 Cangas. No se usa para ningún otro municipio.
ALIAS_POR_CODIGO = {
    "27002": "Alfoz",
    "32023": "Castro Caldelas",
    "36008": "Cangas",
}


def anadir_poblacion(municipios: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    registros, meta = descargar_padron()
    salida = municipios.copy()
    salida["poblacion"] = pd.NA
    salida["anio_poblacion"] = pd.NA
    no_casados: list[str] = []
    if registros.empty:
        salida["poblacion"] = np.nan
        salida["densidad_hab_km2"] = np.nan
        meta["municipios_sin_poblacion"] = [
            f"{fila.nombre} ({fila.provincia})" for fila in salida.itertuples()
        ]
        meta["municipios_con_poblacion"] = 0
        return salida, meta
    for provincia in PROVINCIAS.values():
        locales = registros[registros["provincia"] == provincia]
        indice = list(salida.index[salida["provincia"] == provincia])
        indice.sort(key=lambda idx: len(str(salida.at[idx, "nombre"])), reverse=True)
        usados: set[int] = set()
        for idx in indice:
            elegido = _mejor_cruce(str(salida.at[idx, "nombre"]), locales, usados)
            if elegido is None and str(salida.at[idx, "codigo_ine"]) in ALIAS_POR_CODIGO:
                elegido = _mejor_cruce(ALIAS_POR_CODIGO[str(salida.at[idx, "codigo_ine"])], locales, usados)
            if elegido is None:
                no_casados.append(f"{salida.at[idx, 'nombre']} ({provincia})")
                continue
            usados.add(elegido)
            salida.at[idx, "poblacion"] = int(locales.at[elegido, "poblacion"])
            salida.at[idx, "anio_poblacion"] = int(locales.at[elegido, "anio"])
    salida["poblacion"] = pd.to_numeric(salida["poblacion"], errors="coerce")
    salida["densidad_hab_km2"] = salida["poblacion"] / (salida["area_ha"] / 100.0)
    meta["municipios_sin_poblacion"] = no_casados
    meta["municipios_con_poblacion"] = int(salida["poblacion"].notna().sum())
    logger.info(
        "Población INE: %s municipios con dato, %s sin cruce",
        meta["municipios_con_poblacion"],
        len(no_casados),
    )
    return salida, meta


def descargar_padron() -> tuple[pd.DataFrame, dict]:
    filas = []
    anios = set()
    for codigo_provincia, tabla in TABLAS_INE_POBLACION.items():
        provincia = PROVINCIAS[codigo_provincia]
        series = obtener_json(INE_DATOS.format(tabla=tabla), timeout=120)
        totales = []
        for serie in series:
            nombre = str(serie.get("Nombre") or "")
            if ". Total. Total habitantes" not in nombre:
                continue
            datos = serie.get("Data") or []
            if not datos:
                continue
            valor = datos[0].get("Valor")
            anio = datos[0].get("Anyo")
            if valor is None:
                continue
            municipio = nombre.split(". Total. Total habitantes")[0].strip()
            totales.append({"provincia": provincia, "nombre_ine": municipio, "poblacion": float(valor), "anio": anio})
            if anio:
                anios.add(int(anio))
        if not totales:
            continue
        # El máximo es el total de la provincia, no un concello.
        maximo = max(fila["poblacion"] for fila in totales)
        for fila in totales:
            if fila["poblacion"] == maximo:
                continue
            fila["variantes"] = variantes_toponimo(fila["nombre_ine"])
            filas.append(fila)
    tabla = pd.DataFrame(filas)
    meta = {
        "fuente": "INE padrón municipal, tablas provinciales DPOP",
        "tablas": TABLAS_INE_POBLACION,
        "anios": sorted(anios),
        "registros": int(len(tabla)),
    }
    return tabla, meta


def _mejor_cruce(nombre: str, locales: pd.DataFrame, usados: set[int]) -> int | None:
    variantes = variantes_toponimo(nombre)
    mejor = None
    mejor_largo = -1
    for indice, fila in locales.iterrows():
        if indice in usados:
            continue
        comunes = variantes & fila["variantes"]
        if not comunes:
            continue
        largo = max(len(comun) for comun in comunes)
        if largo > mejor_largo:
            mejor_largo = largo
            mejor = int(indice)
    return mejor


def normalizar_toponimo(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in descompuesto if not unicodedata.combining(c))
    limpio = sin_acentos.lower().replace("’", "'").replace("'", "")
    limpio = limpio.replace(".", " ")
    limpio = re.sub(r"[^a-z0-9,\s]", " ", limpio)
    return re.sub(r"\s+", " ", limpio).strip()


def variantes_toponimo(texto: str) -> set[str]:
    base = normalizar_toponimo(texto)
    variantes = {base}
    if "," in base:
        izquierda, derecha = [parte.strip() for parte in base.split(",", 1)]
        if derecha in ARTICULOS:
            variantes.add(f"{derecha} {izquierda}")
            variantes.add(izquierda)
    partes = base.split()
    if partes and partes[0] in ARTICULOS and len(partes) > 1:
        resto = " ".join(partes[1:])
        variantes.add(f"{resto}, {partes[0]}")
        variantes.add(resto)
    return {variante for variante in variantes if variante}
