from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from shapely.geometry import box

from prioridad_galicia.geo import crear_rejilla, estadistica_zonal, rasterizar_zonas
from prioridad_galicia.sources.nisar import filtro_mediana, gamma0_a_db, leer_gcov
from prioridad_galicia.sources.sentinel1 import fraccion_bbox, preparar_retrodispersion, seleccionar_escenas
from prioridad_galicia.validation import evaluar


def test_gamma0_a_db_de_la_decima_parte():
    decibelios = gamma0_a_db(np.array([0.1, 0.0, np.nan], dtype=np.float32))
    assert abs(decibelios[0] - (-10)) < 1e-4
    assert np.isnan(decibelios[1]) and np.isnan(decibelios[2])


def test_retrodispersion_lineal_y_ya_en_db():
    lineal = np.array([[0.1, 0.01], [0.2, -32768]], dtype=np.float32)
    decibelios, modo = preparar_retrodispersion(lineal, nodata=-32768)
    assert modo == "lineal_a_db"
    assert abs(decibelios[0, 0] - (-10)) < 1e-3
    assert np.isnan(decibelios[1, 1])
    ya_db = np.array([[-12.0, -14.0], [-11.0, -13.0]], dtype=np.float32)
    mismo, modo_db = preparar_retrodispersion(ya_db, nodata=None)
    assert modo_db == "ya_db"
    assert abs(mismo[0, 0] - (-12)) < 1e-6


def test_filtro_mediana_ignora_nan():
    datos = np.array([[1.0, np.nan], [1.0, 1.0]], dtype=np.float32)
    filtrado = filtro_mediana(datos, size=3)
    assert np.isfinite(filtrado[1, 1])
    assert abs(filtrado[1, 1] - 1) < 1e-6


def test_leer_gcov_prefiere_hvhv_de_banda_l(tmp_path: Path):
    ruta = tmp_path / "falso_gcov.h5"
    ys = np.linspace(4_800_000, 4_799_000, 8)
    xs = np.linspace(500_000, 501_000, 6)
    with h5py.File(ruta, "w") as hdf:
        grupo = hdf.create_group("/science/LSAR/GCOV/grids/frequencyA")
        grupo.create_dataset("xCoordinates", data=xs)
        grupo.create_dataset("yCoordinates", data=ys)
        grupo.create_dataset("HHHH", data=np.full((8, 6), 0.05))
        grupo.create_dataset("HVHV", data=np.full((8, 6), 0.1))
        grupo.attrs["epsg"] = 32629
        banda_s = hdf.create_group("/science/LSAR/GCOV/grids/frequencyB")
        banda_s.create_dataset("xCoordinates", data=xs)
        banda_s.create_dataset("yCoordinates", data=ys)
        banda_s.create_dataset("HVHV", data=np.full((8, 6), 0.02))
        banda_s.attrs["epsg"] = 32629
    decibelios, _transform, crs, info = leer_gcov(ruta, resolucion_objetivo_m=20)
    assert info["polarizacion"] == "HVHV"
    assert info["frecuencia"] == "L"
    assert info["modo_db"] == "lineal_a_db"
    assert crs.to_epsg() == 32629
    assert abs(float(np.nanmedian(decibelios)) - (-10)) < 0.2


def test_zonal_mediana_en_dos_cajas():
    alto, ancho, transform = crear_rejilla((0, 0, 100, 100), 10)
    valores = np.arange(alto * ancho, dtype=np.float32).reshape(alto, ancho)
    geometrias = [box(0, 0, 40, 40), box(60, 60, 100, 100)]
    zonas = rasterizar_zonas(geometrias, alto, ancho, transform)
    medias = estadistica_zonal(zonas, valores, 2, "median")
    assert np.isfinite(medias).all()
    assert medias[0] != medias[1]


def test_seleccion_de_escenas_limita_el_numero():
    class Item:
        def __init__(self, identificador, bbox, semana):
            self.id = identificador
            self.bbox = bbox
            self.datetime = __import__("datetime").datetime.fromisoformat(f"2024-07-{semana:02d}T12:00:00+00:00")

    # El ámbito de config es aproximadamente -9.45, 41.7, -6.55, 43.95.
    oeste = [-9.4, 41.8, -8.2, 43.8]
    este = [-8.0, 41.8, -6.6, 43.8]
    items = [Item(f"w{i}", oeste if i % 2 == 0 else este, min(28, 1 + i)) for i in range(1, 12)]
    elegidas = seleccionar_escenas(items, max_escenas=4)
    assert 1 <= len(elegidas) <= 4
    assert fraccion_bbox(oeste, (-9.45, 41.70, -6.55, 43.95)) > 0.2


def test_evaluar_concentra_las_hectareas_en_la_prioridad_alta():
    tabla = pd.DataFrame(
        {
            "prioridad": [10, 20, 30, 40, 90, 95, 97, 99, 50, 60],
            "ha_quemadas_val": [0, 0, 0, 0, 0, 0, 0, 100, 0, 0],
        }
    )
    resumen = evaluar(tabla)
    assert resumen["captura"]["top_10"]["fraccion_ha"] == 1
    assert resumen["auc"] == 1
