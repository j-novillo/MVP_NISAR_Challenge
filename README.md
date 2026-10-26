# Prioridad territorial para incendios forestales en Galicia

Herramienta del reto **Dancing with the SARs** (NASA Space Apps 2026). Cruza radar (Sentinel-1 y, cuando hay token, NISAR), el historial de área quemada, el peligro meteorológico, la población y la accesibilidad, y ordena los **municipios de Galicia** según dónde actuar primero.

La prioridad de un municipio es una suma de cinco componentes entre 0 y 1, con pesos a la vista:

`P = 100 · (w1·combustible SAR + w2·historial + w3·FWI + w4·exposición + w5·dificultad de acceso)`

No es un modelo opaco. Los pesos por defecto están justificados en [`docs/indice_y_pesos.md`](docs/indice_y_pesos.md) y se mueven en el visor, con un preset para bombero, otro para gestión forestal y otro para protección civil.

El ámbito es Galicia (A Coruña, Lugo, Ourense y Pontevedra). La geometría es la del IGN y el cálculo métrico está en **EPSG:25830**. No se usa Google Earth Engine.

## Arranque rápido

El índice ya calculado viaja en `data/processed/`. Para verlo:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
streamlit run app/visor.py
```

Para rehacer todas las descargas y el índice:

```bash
python -m prioridad_galicia.cli pipeline
```

Para procesar NISAR con un token de NASA Earthdata (la búsqueda del catálogo no lo necesita; la descarga sí):

```bash
export EARTHDATA_TOKEN="el_token_que_no_se_sube_al_repositorio"
python -m prioridad_galicia.cli nisar-procesar --max-escenas 8 --escenas PREFIJO_DEL_TITULO
```

Las ocho escenas de octubre de 2026 ya están agregadas en `data/processed/`. Los prefijos exactos y el motivo del Bearer (la cuenta aún no ha aceptado la EULA de ASF) están en [`docs/fuentes/nisar.md`](docs/fuentes/nisar.md).

El detalle de cada comando, de la caché y de qué fichero es cada salida está en [`docs/como_ejecutar.md`](docs/como_ejecutar.md). La plantilla del secreto es [`.env.example`](.env.example).

## Qué hay en el repositorio

| Ruta | Para qué |
|---|---|
| `src/prioridad_galicia/` | Pipeline, fuentes, índice y validación. |
| `app/visor.py` | Mapa coroplético, top 10, ficha y pesos. |
| `docs/datos_satelite_sar.md` | Qué es el SAR, bandas L y C, GCOV y RTC, y cómo el código busca, recorta, pasa a dB, filtra y agrega. |
| `docs/` | Arquitectura, cada fuente, cada fase, pesos, visor, validación y limitaciones. |
| `data/processed/` | GeoJSON, GeoPackage, CSV, catálogo NISAR, validación y manifiesto. Sin rásteres. |
| `tests/` | Normalización, pesos, lector GCOV sintético, zonal y AUC. |

## Ejecución incluida en `data/processed`

Estos números son los de la corrida que generó los ficheros del repositorio (octubre de 2026). Si se relanza el pipeline, manda [`data/processed/manifiesto.json`](data/processed/manifiesto.json).

- 313 municipios del WFS del IGN, con población del padrón 2025 en los 313 (tres cruces por código, porque el topónimo del IGN y el del INE no coinciden: Alfoz, Castro Caldelas y Cangas).
- Sentinel-1 RTC: 129 escenas de junio a septiembre de 2024 en el catálogo; la mediana usa 8 (órbitas ascendente y descendente). VH municipal entre unos −18,6 y −12,2 dB. Los ocho rásteres se leyeron como gamma0 lineal y se pasaron a dB.
- NISAR L2 GCOV sobre el recuadro de Galicia: **131 escenas** en el catálogo (113 provisionales y 18 beta). De ellas se procesaron **8** gránulos reales (13, 18 y 20 de octubre de 2026, HVHV, banda L). Cubren los **313** municipios, con HV entre **−19,7 y −10,3 dB**. La correlación con el VH de Sentinel-1 es **r = 0,57**. No entran en el índice por defecto: son posteriores a la validación 2025–2026. El visor las enseña con un interruptor, apagado al abrir. La descarga usó Bearer directo porque la cuenta aún no ha aceptado la EULA de ASF (`auth_with_token` devolvía 403).
- Historial EFFIS 2010–2024: 1050 perímetros. Validación 2025–2026: 434 perímetros, unas 128 600 ha en la intersección municipal.
- FWI: las seis fechas de 2024 respondieron. WorldCover 2021 cubre los 313 municipios. OSM: 88 parques de bomberos y 30 653 tramos de vía principal.
- Con el preset equilibrado, el 10 % de municipios con más prioridad concentra el **39,7 %** de las hectáreas de 2025–2026 (el azar dejaría un 10 %). El 30 % concentra el 78 %. El AUC de “ardió algo” es 0,68. Las hectáreas por quintil crecen de Q1 a Q5.
- Incendib abre la portada y anuncia que está en pausa: no hay descarga. El CSV municipal de la Xunta (2001–2006) no respondió a tiempo y, aunque respondiera, no entraría en el índice porque la serie abierta se corta en 2006.

## Documentación

1. [Arquitectura](docs/arquitectura.md)
2. [Datos de satélite SAR](docs/datos_satelite_sar.md) — el documento largo
3. [Índice y pesos](docs/indice_y_pesos.md)
4. [Cómo ejecutarlo](docs/como_ejecutar.md)
5. [Visor](docs/visor.md)
6. [Validación 2025–2026](docs/validacion.md)
7. [Limitaciones](docs/limitaciones.md)
8. Fases: [entorno](docs/fases/fase0_entorno.md), [territorio](docs/fases/fase1_territorio.md), [SAR](docs/fases/fase2_sar.md), [auxiliares](docs/fases/fase3_auxiliares.md), [índice](docs/fases/fase4_indice.md), [validación](docs/fases/fase5_validacion.md)
9. Fuentes: [IGN](docs/fuentes/territorio.md), [Sentinel-1](docs/fuentes/sentinel1.md), [NISAR](docs/fuentes/nisar.md), [incendios](docs/fuentes/incendios.md), [FWI](docs/fuentes/fwi.md), [INE](docs/fuentes/poblacion.md), [OSM](docs/fuentes/osm.md), [WorldCover](docs/fuentes/worldcover.md)

## Degradación

Si una fuente no responde, su columna queda vacía y el peso de ese componente se reparte entre los que sí existen. No hay municipios de relleno ni un FWI copiado de un año inventado. El combustible del índice es la mediana de Sentinel-1 RTC del verano de 2024. NISAR, aunque ya está agregado, se queda fuera de esa fórmula: las ocho escenas son de octubre de 2026 y habrían visto parte de los incendios con los que se valida.

## Licencias de los datos

El código de este repositorio no relicencia los datos. Cada fuente conserva la suya: IGN (CC BY 4.0), INE, EFFIS / Copernicus (CC BY 4.0), ESA WorldCover, OpenStreetMap (ODbL), Sentinel-1 (Copernicus) y NISAR (NASA/ISRO, uso sujeto a Earthdata). El manifiesto y las fichas de `docs/fuentes/` dicen cuál entró en cada columna.
