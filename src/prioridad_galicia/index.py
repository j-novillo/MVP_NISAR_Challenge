"""Índice de prioridad y componentes 0–1.

P_i = 100 · (w1·COMB + w2·HIST + w3·FWI + w4·EXPO + w5·ACCES)

Si a un municipio le falta un componente, su peso se reparte entre los que sí
tiene. No se rellena con ceros ni con la media de Galicia.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from prioridad_galicia.config import (
    COMPONENTES,
    PESOS_ACCES,
    PESOS_COMB,
    PESOS_EXPO,
    PESOS_HIST,
    PRESETS,
)
from prioridad_galicia.normalize import media_ponderada, robust_minmax


def normalizar_pesos(pesos: dict[str, float]) -> dict[str, float]:
    """Devuelve pesos no negativos que suman 1. Ignora claves ajenas al índice."""
    limpio = {componente: max(0.0, float(pesos.get(componente, 0.0))) for componente in COMPONENTES}
    total = sum(limpio.values())
    if total <= 0:
        uniforme = 1.0 / len(COMPONENTES)
        return {componente: uniforme for componente in COMPONENTES}
    return {componente: valor / total for componente, valor in limpio.items()}


def construir_componentes(tabla: pd.DataFrame) -> pd.DataFrame:
    """Añade comb, hist, fwi, expo y acces en 0–1 a partir de las columnas crudas."""
    salida = tabla.copy()
    vh = robust_minmax(salida["vh_db"]) if "vh_db" in salida else _nan(salida)
    ratio = robust_minmax(salida["ratio_vh_vv_db"]) if "ratio_vh_vv_db" in salida else _nan(salida)
    salida["comb"] = media_ponderada({"vh": vh, "ratio": ratio}, PESOS_COMB)

    if "n_incendios_hist" in salida:
        n_hist = robust_minmax(np.log1p(salida["n_incendios_hist"].astype(float)))
    else:
        n_hist = _nan(salida)
    if "ha_quemadas_1000ha_hist" in salida:
        ha_hist = robust_minmax(np.log1p(salida["ha_quemadas_1000ha_hist"].astype(float)))
    else:
        ha_hist = _nan(salida)
    salida["hist"] = media_ponderada({"n": n_hist, "ha": ha_hist}, PESOS_HIST)

    salida["fwi"] = robust_minmax(salida["fwi_medio"]) if "fwi_medio" in salida else _nan(salida)

    if "poblacion" in salida:
        poblacion = robust_minmax(np.log1p(salida["poblacion"].astype(float)))
    else:
        poblacion = _nan(salida)
    if "densidad_hab_km2" in salida:
        densidad = robust_minmax(salida["densidad_hab_km2"])
    else:
        densidad = _nan(salida)
    salida["expo"] = media_ponderada({"poblacion": poblacion, "densidad": densidad}, PESOS_EXPO)

    if "dist_parque_km" in salida:
        distancia = robust_minmax(salida["dist_parque_km"])
    else:
        distancia = _nan(salida)
    if "densidad_viaria" in salida:
        # Más kilómetros de vía principal por km² = llegada más fácil = menos prioridad.
        inversa = 1.0 / (salida["densidad_viaria"].astype(float) + 0.05)
        viaria = robust_minmax(inversa.where(salida["densidad_viaria"].notna()))
    else:
        viaria = _nan(salida)
    salida["acces"] = media_ponderada({"distancia": distancia, "viaria": viaria}, PESOS_ACCES)
    return salida


def calcular_prioridad(tabla: pd.DataFrame, pesos: dict[str, float] | None = None) -> pd.DataFrame:
    """Añade ``prioridad`` (0–100) y ``factor_dominante``."""
    pesos_ok = normalizar_pesos(pesos or PRESETS["equilibrado"])
    matriz = tabla.loc[:, list(COMPONENTES)].to_numpy(dtype=float)
    presente = np.isfinite(matriz)
    vector = np.array([pesos_ok[componente] for componente in COMPONENTES], dtype=float)
    pesos_fila = presente * vector
    denominador = pesos_fila.sum(axis=1)
    numerador = np.nansum(np.where(presente, matriz * vector, 0.0), axis=1)
    puntuacion = np.full(denominador.shape, np.nan, dtype=float)
    np.divide(numerador, denominador, out=puntuacion, where=denominador > 0)
    puntuacion = np.where(denominador > 0, puntuacion * 100.0, np.nan)
    aportes = np.where(presente, matriz * vector, -np.inf)
    ganador = np.argmax(aportes, axis=1)
    factores = []
    for fila, columna in enumerate(ganador):
        if not presente[fila].any():
            factores.append(pd.NA)
        else:
            factores.append(COMPONENTES[int(columna)])
    salida = tabla.copy()
    salida["prioridad"] = puntuacion
    salida["factor_dominante"] = factores
    return salida


def _nan(tabla: pd.DataFrame) -> pd.Series:
    return pd.Series(np.nan, index=tabla.index, dtype="float64")
