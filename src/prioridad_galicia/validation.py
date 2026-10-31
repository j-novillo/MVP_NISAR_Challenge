"""Validación retrospectiva: ¿el índice concentra las hectáreas quemadas en 2025–2026?"""

from __future__ import annotations

import numpy as np
import pandas as pd


def roc_auc(clases: np.ndarray, puntuacion: np.ndarray) -> float | None:
    """AUC de Mann–Whitney. ``clases`` es booleano (True = ardió algo)."""
    y = np.asarray(clases, dtype=bool)
    score = np.asarray(puntuacion, dtype=float)
    n_pos = int(y.sum())
    n_neg = int((~y).sum())
    if n_pos == 0 or n_neg == 0:
        return None
    orden = np.argsort(score, kind="mergesort")
    rangos = np.empty(score.size, dtype=float)
    rangos[orden] = np.arange(1, score.size + 1, dtype=float)
    # Empates: rango medio.
    ordenado = score[orden]
    inicio = 0
    while inicio < ordenado.size:
        fin = inicio + 1
        while fin < ordenado.size and ordenado[fin] == ordenado[inicio]:
            fin += 1
        if fin - inicio > 1:
            medio = (inicio + 1 + fin) / 2.0
            rangos[orden[inicio:fin]] = medio
        inicio = fin
    suma_positivos = float(rangos[y].sum())
    return (suma_positivos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def evaluar(tabla: pd.DataFrame, columna_prioridad: str = "prioridad", columna_ha: str = "ha_quemadas_val") -> dict:
    """Captura de hectáreas en el top territorial y AUC de 'ardió / no ardió'."""
    trabajo = tabla[[columna_prioridad, columna_ha]].copy()
    trabajo[columna_ha] = trabajo[columna_ha].fillna(0.0)
    trabajo = trabajo[np.isfinite(trabajo[columna_prioridad].to_numpy())]
    trabajo = trabajo.sort_values(columna_prioridad, ascending=False)
    total_ha = float(trabajo[columna_ha].sum())
    n = int(len(trabajo))
    captura = {}
    for fraccion in (0.10, 0.20, 0.30):
        k = max(1, int(np.ceil(n * fraccion))) if n else 0
        obtenido = float(trabajo[columna_ha].iloc[:k].sum()) if k else 0.0
        captura[f"top_{int(fraccion * 100)}"] = {
            "municipios": k,
            "ha": round(obtenido, 2),
            "fraccion_ha": None if total_ha <= 0 else round(obtenido / total_ha, 4),
            "azar": fraccion,
        }
    clases = trabajo[columna_ha].to_numpy() > 0
    auc = roc_auc(clases, trabajo[columna_prioridad].to_numpy())
    quintiles = _resumen_quintiles(trabajo, columna_prioridad, columna_ha)
    return {
        "n_municipios": n,
        "ha_quemadas_validacion": round(total_ha, 2),
        "municipios_con_fuego": int(clases.sum()) if n else 0,
        "captura": captura,
        "auc": None if auc is None else round(float(auc), 4),
        "quintiles": quintiles,
    }


def _resumen_quintiles(trabajo: pd.DataFrame, columna_prioridad: str, columna_ha: str) -> list[dict]:
    if len(trabajo) < 5:
        return []
    try:
        grupos = pd.qcut(trabajo[columna_prioridad], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
    except ValueError:
        return []
    filas = []
    for etiqueta, bloque in trabajo.groupby(grupos, observed=True):
        filas.append(
            {
                "quintil": str(etiqueta),
                "municipios": int(len(bloque)),
                "ha": round(float(bloque[columna_ha].sum()), 2),
                "ha_media": round(float(bloque[columna_ha].mean()), 2),
                "prioridad_media": round(float(bloque[columna_prioridad].mean()), 2),
            }
        )
    return filas


def figura_quintiles(resumen: dict):
    """Gráfico de barras: hectáreas de 2025–2026 por quintil de prioridad."""
    import matplotlib.pyplot as plt

    quintiles = resumen.get("quintiles") or []
    figura, eje = plt.subplots(figsize=(7.2, 4.2))
    if not quintiles:
        eje.text(0.5, 0.5, "Sin suficientes municipios para quintiles", ha="center")
        eje.axis("off")
        return figura
    etiquetas = [fila["quintil"] for fila in quintiles]
    hectareas = [fila["ha"] for fila in quintiles]
    colores = ["#f5e6c8", "#f0c98a", "#e89b4d", "#d06a2b", "#9a3412"]
    eje.bar(etiquetas, hectareas, color=colores[: len(etiquetas)], edgecolor="#44403c")
    eje.set_ylabel("Hectáreas quemadas 2025–2026 (EFFIS)")
    eje.set_xlabel("Quintil de prioridad (Q1 baja → Q5 alta)")
    eje.set_title("¿Las hectáreas caen en los municipios que el índice marca primero?")
    eje.spines["top"].set_visible(False)
    eje.spines["right"].set_visible(False)
    figura.tight_layout()
    return figura
