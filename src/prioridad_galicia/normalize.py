"""Normalización robusta a 0–1. No imputa huecos."""

from __future__ import annotations

import numpy as np
import pandas as pd

from prioridad_galicia.config import PERCENTIL_ALTO, PERCENTIL_BAJO


def robust_minmax(
    valores: pd.Series | np.ndarray,
    p_bajo: float = PERCENTIL_BAJO,
    p_alto: float = PERCENTIL_ALTO,
) -> pd.Series:
    """Escala entre los percentiles ``p_bajo`` y ``p_alto`` y recorta a [0, 1].

    Los valores no finitos siguen siendo NaN. Si la serie es constante, los
    finitos valen 0,5: no hay contraste territorial que inventar.
    """
    serie = pd.to_numeric(pd.Series(valores), errors="coerce").astype("float64")
    finitos = serie[np.isfinite(serie.to_numpy())]
    salida = pd.Series(np.nan, index=serie.index, dtype="float64")
    if finitos.empty:
        return salida
    if finitos.size == 1 or float(finitos.max() - finitos.min()) < 1e-12:
        salida.loc[finitos.index] = 0.5
        return salida
    bajo = float(np.nanpercentile(finitos.to_numpy(), p_bajo))
    alto = float(np.nanpercentile(finitos.to_numpy(), p_alto))
    if alto - bajo < 1e-12:
        salida.loc[finitos.index] = 0.5
        return salida
    escalada = ((serie - bajo) / (alto - bajo)).clip(lower=0.0, upper=1.0)
    escalada[~np.isfinite(serie.to_numpy())] = np.nan
    return escalada


def media_ponderada(componentes: dict[str, pd.Series], pesos: dict[str, float]) -> pd.Series:
    """Combina series 0–1. En cada fila reparte el peso entre los valores finitos.

    Un NaN no se convierte en cero: si solo hay retrodispersión VH y falta el
    ratio, el componente vale lo que valga VH.
    """
    utiles = [(clave, serie) for clave, serie in componentes.items() if serie is not None]
    if not utiles:
        raise ValueError("media_ponderada necesita al menos una serie")
    marco = pd.DataFrame({clave: serie.astype(float) for clave, serie in utiles})
    peso = np.array([float(pesos[clave]) for clave, _ in utiles], dtype=float)
    valores = marco.to_numpy(dtype=float)
    presente = np.isfinite(valores)
    pesos_fila = presente * peso
    denominador = pesos_fila.sum(axis=1)
    numerador = np.nansum(np.where(presente, valores * peso, 0.0), axis=1)
    salida = np.full(denominador.shape, np.nan, dtype=float)
    np.divide(numerador, denominador, out=salida, where=denominador > 0)
    return pd.Series(salida, index=marco.index, dtype="float64")
