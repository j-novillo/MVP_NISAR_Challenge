"""Constantes del ámbito, de las fuentes y de los pesos del índice.

Los pesos viven aquí para que el pipeline, el visor y los tests usen la misma
definición. La justificación larga está en ``docs/indice_y_pesos.md``.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
CACHE = DATA / "cache"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"

# Galicia continental e islas administrativas. El recuadro es holgado a propósito
# para no cortar concellos costeros; el filtro por código INE descarta vecinos.
BBOX_OESTE = -9.45
BBOX_SUR = 41.70
BBOX_ESTE = -6.55
BBOX_NORTE = 43.95
BBOX_LONLAT = (BBOX_OESTE, BBOX_SUR, BBOX_ESTE, BBOX_NORTE)
# WFS 2.0 del IGN con URN geográfico: el orden del bbox es lat, lon.
BBOX_WFS = f"{BBOX_SUR},{BBOX_OESTE},{BBOX_NORTE},{BBOX_ESTE}"

CRS_TRABAJO = "EPSG:25830"
CRS_GEOGRAFICO = "EPSG:4258"

PROVINCIAS = {
    "15": "A Coruña",
    "27": "Lugo",
    "32": "Ourense",
    "36": "Pontevedra",
}
# Nombres que acepta el filtro ``province`` de la API de EFFIS.
PROVINCIAS_EFFIS = ["A Coruña", "Lugo", "Ourense", "Pontevedra"]

# Tablas del padrón municipal (INE, operación DPOP) por provincia.
TABLAS_INE_POBLACION = {
    "15": 2868,
    "27": 2880,
    "32": 2885,
    "36": 2890,
}

WFS_IGN = "https://www.ign.es/wfs-inspire/unidades-administrativas"
INE_DATOS = "https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{tabla}?nult=1"
EFFIS_BURNT = "https://api.effis.emergency.copernicus.eu/rest/2/burntareas/current/"
EFFIS_WMS = "https://maps.effis.emergency.copernicus.eu/effis"
STAC_PC = "https://planetarycomputer.microsoft.com/api/stac/v1"
CMR_GRANULES = "https://cmr.earthdata.nasa.gov/search/granules.json"

# Historial que entra en el índice: anterior a la ventana de validación.
HIST_INICIO = "2010-01-01"
HIST_FIN = "2024-12-31"
VAL_INICIO = "2025-01-01"
VAL_FIN = "2026-12-31"

# Estado del combustible anterior a los incendios con los que validamos.
S1_INICIO = "2024-06-01"
S1_FIN = "2024-09-15"
S1_COLECCION = "sentinel-1-rtc"
S1_MAX_ESCENAS = 8
S1_RESOLUCION_M = 400

# Peligro meteorológico de la campaña previa (no usa área quemada).
FWI_FECHAS = (
    "2024-06-15",
    "2024-07-01",
    "2024-07-15",
    "2024-08-01",
    "2024-08-15",
    "2024-09-01",
)
FWI_CAPA = "mf010.fwi"

# NISAR L2 GCOV. La búsqueda CMR es pública; la descarga no.
NISAR_COLECCIONES = (
    "NISAR_L2_GCOV_PROVISIONAL_V1",
    "NISAR_L2_GCOV_BETA_V1",
)
POLARIZACIONES_POTENCIA = ("HHHH", "HVHV", "VVVV")
POLARIZACIONES_CRUZADAS = ("HVHV", "HHHV", "VVVH")

OVERPASS_SERVIDORES = (
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

USER_AGENT = "prioridad-galicia-mvp/0.1 (NASA Space Apps; uso de datos abiertos)"

# Percentiles del min-max robusto. Recortan colas sin borrar el orden.
PERCENTIL_BAJO = 5.0
PERCENTIL_ALTO = 95.0

COMPONENTES = ("comb", "hist", "fwi", "expo", "acces")

# Pesos internos de cada componente (suman 1). El índice solo ve el resultado 0–1.
PESOS_COMB = {"vh": 0.55, "ratio": 0.45}
PESOS_HIST = {"n": 0.45, "ha": 0.55}
PESOS_EXPO = {"poblacion": 0.60, "densidad": 0.40}
PESOS_ACCES = {"distancia": 0.65, "viaria": 0.35}

PRESETS: dict[str, dict[str, float]] = {
    "equilibrado": {"comb": 0.30, "hist": 0.25, "fwi": 0.20, "expo": 0.15, "acces": 0.10},
    "bombero": {"comb": 0.15, "hist": 0.20, "fwi": 0.25, "expo": 0.15, "acces": 0.25},
    "forestal": {"comb": 0.40, "hist": 0.30, "fwi": 0.15, "expo": 0.05, "acces": 0.10},
    "proteccion_civil": {"comb": 0.10, "hist": 0.15, "fwi": 0.25, "expo": 0.35, "acces": 0.15},
}

ETIQUETAS = {
    "comb": "Combustible (SAR)",
    "hist": "Historial de incendios",
    "fwi": "Peligro meteorológico (FWI)",
    "expo": "Exposición (población)",
    "acces": "Dificultad de acceso",
}

NOMBRES_PRESET = {
    "equilibrado": "Equilibrado (gestor de prevención)",
    "bombero": "Bombero",
    "forestal": "Forestal",
    "proteccion_civil": "Protección civil",
}

JUSTIFICACION_CORTA = {
    "equilibrado": (
        "Quien planifica la campaña actúa sobre combustible e historial (55 %), "
        "mira el peligro meteorológico (20 %) y reserva el resto a población y acceso."
    ),
    "bombero": (
        "El despliegue depende de si el medio llega y de si el día es extremo: "
        "acceso y FWI pesan la mitad; el combustible contextualiza."
    ),
    "forestal": (
        "La prevención selvícola trata biomasa y recurrencia. El 70 % del índice "
        "es combustible SAR más historial."
    ),
    "proteccion_civil": (
        "La prioridad es proteger a las personas: exposición y peligro meteorológico "
        "suman 60 %, y el acceso condiciona la evacuación."
    ),
}

SALIDA_GEOJSON = PROCESSED / "municipios_indice.geojson"
SALIDA_GPKG = PROCESSED / "municipios_indice.gpkg"
SALIDA_CSV = PROCESSED / "municipios_indice.csv"
SALIDA_NISAR = PROCESSED / "nisar_escenas_galicia.json"
SALIDA_NISAR_ZONAL = PROCESSED / "nisar_municipios.csv"
SALIDA_NISAR_LECTURA = PROCESSED / "nisar_lectura.json"
SALIDA_MANIFIESTO = PROCESSED / "manifiesto.json"
SALIDA_VALIDACION = PROCESSED / "validacion.json"
SALIDA_FIGURA = PROCESSED / "validacion_quintiles.png"
