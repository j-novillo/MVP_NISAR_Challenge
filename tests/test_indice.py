import numpy as np
import pandas as pd
import pytest

from prioridad_galicia.config import COMPONENTES, PRESETS
from prioridad_galicia.index import calcular_prioridad, construir_componentes, normalizar_pesos
from prioridad_galicia.normalize import media_ponderada, robust_minmax
from prioridad_galicia.sources.poblacion import variantes_toponimo
from prioridad_galicia.validation import roc_auc


def test_minmax_recorta_colas_y_conserva_nan():
    serie = pd.Series([0, 1, 2, 3, 4, 100, np.nan])
    salida = robust_minmax(serie, p_bajo=0, p_alto=100)
    assert salida.iloc[-1] != salida.iloc[-1]
    assert salida.iloc[0] == 0
    assert salida.iloc[5] == 1
    assert salida.iloc[2] == 0.02


def test_minmax_constante_vale_un_medio():
    salida = robust_minmax(pd.Series([3.0, 3.0, np.nan]))
    assert salida.iloc[0] == 0.5
    assert np.isnan(salida.iloc[2])


def test_media_ponderada_no_convierte_nan_en_cero():
    resultado = media_ponderada(
        {
            "vh": pd.Series([0.8, 0.2]),
            "ratio": pd.Series([np.nan, 0.4]),
        },
        {"vh": 0.5, "ratio": 0.5},
    )
    assert resultado.iloc[0] == 0.8
    assert resultado.iloc[1] == pytest.approx(0.3)


def test_pesos_de_presets_suman_uno():
    for pesos in PRESETS.values():
        assert set(pesos) == set(COMPONENTES)
        assert abs(sum(pesos.values()) - 1) < 1e-9
    renormalizados = normalizar_pesos({"comb": 2, "hist": 2, "fwi": 0, "expo": 0, "acces": 0})
    assert abs(renormalizados["comb"] - 0.5) < 1e-9
    assert renormalizados["fwi"] == 0


def test_prioridad_reparte_el_peso_de_un_hueco():
    tabla = pd.DataFrame(
        {
            "comb": [1.0],
            "hist": [0.0],
            "fwi": [np.nan],
            "expo": [0.0],
            "acces": [0.0],
        }
    )
    pesos = {"comb": 0.5, "hist": 0.5, "fwi": 0.0, "expo": 0.0, "acces": 0.0}
    salida = calcular_prioridad(tabla, pesos)
    assert salida.loc[0, "prioridad"] == 50
    assert salida.loc[0, "factor_dominante"] == "comb"


def test_componentes_dejan_nan_si_no_hay_sar():
    tabla = pd.DataFrame(
        {
            "vh_db": [np.nan, np.nan],
            "ratio_vh_vv_db": [np.nan, np.nan],
            "n_incendios_hist": [0, 4],
            "ha_quemadas_1000ha_hist": [0, 10],
            "fwi_medio": [5, 40],
            "poblacion": [100, 50000],
            "densidad_hab_km2": [10, 800],
            "dist_parque_km": [2, 30],
            "densidad_viaria": [1.2, 0.1],
        }
    )
    salida = construir_componentes(tabla)
    assert salida["comb"].isna().all()
    assert salida["hist"].notna().all()


def test_toponimos_con_articulo():
    assert variantes_toponimo("A Coruña") & variantes_toponimo("Coruña, A")
    assert variantes_toponimo("O Irixo") & variantes_toponimo("Irixo, O")


def test_auc_perfecta_y_nula():
    assert roc_auc(np.array([True, False]), np.array([2.0, 1.0])) == 1
    assert roc_auc(np.array([True, False]), np.array([1.0, 2.0])) == 0
    assert roc_auc(np.array([True, True]), np.array([1.0, 2.0])) is None
