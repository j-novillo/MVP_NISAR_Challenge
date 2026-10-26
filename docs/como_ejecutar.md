# Cómo ejecutarlo

Hace falta Python 3.11 o superior. En esta máquina se usó 3.12. Todo corre en local: no hay servicio que desplegar para obtener el índice.

## 1. Entorno

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

`requirements.txt` fija las versiones con las que se generó el índice que viaja en `data/processed/`. `pip install -e .` deja importable el paquete `prioridad_galicia`.

Atajo, si `make` está disponible: `make install`.

## 2. Pipeline completo

```bash
python -m prioridad_galicia.cli pipeline
```

Opciones:

| Argumento | Defecto | Efecto |
|---|---|---|
| `--max-escenas-s1` | 8 | Cuántas escenas Sentinel-1 RTC entran en la mediana. |
| `--resolucion` | 400 | Lado del píxel de la rejilla SAR, en metros. |
| `--forzar` | apagado | Ignora la caché de municipios y de escenas ya leídas. |

La primera ejecución descarga municipios, padrón, perímetros EFFIS, FWI, OSM y lee ventanas COG de Sentinel-1. Puede tardar, según la red, del orden de unas decenas de minutos. La segunda, con caché caliente, salta las escenas ya reproyectadas.

Salidas, todas ligeras y en el repositorio:

| Fichero | Qué es |
|---|---|
| `data/processed/municipios_indice.geojson` | Municipios en EPSG:4326 con componentes, prioridad y procedencia. Lo abre el visor. |
| `data/processed/municipios_indice.gpkg` | Lo mismo en EPSG:25830. |
| `data/processed/municipios_indice.csv` | Tabla sin geometría. |
| `data/processed/nisar_escenas_galicia.json` | Inventario público de escenas NISAR GCOV. |
| `data/processed/validacion.json` | Captura de hectáreas, AUC y quintiles del preset equilibrado. |
| `data/processed/validacion_quintiles.png` | El gráfico de esa validación. |
| `data/processed/manifiesto.json` | Qué fase funcionó, cuál falló y con qué fuente. |

No se versionan `data/cache/`, `data/raw/`, los TIFF ni los HDF5.

## 3. NISAR con token

La búsqueda no pide nada:

```bash
python -m prioridad_galicia.cli nisar-buscar
```

El procesado sí. El token no se escribe en ningún fichero del repo. Se exporta en la sesión:

```bash
export EARTHDATA_TOKEN="pega_aqui_el_token_de_earthdata"
python -m prioridad_galicia.cli nisar-procesar --max-escenas 2
```

También vale un `.env` en la raíz (está en `.gitignore`; la plantilla es `.env.example`):

```bash
cp .env.example .env
# edita EARTHDATA_TOKEN
python -m prioridad_galicia.cli nisar-procesar --max-escenas 2
```

Eso descarga hasta dos HDF5 GCOV (cientos de MB cada uno), lee el HV de banda L, lo pasa a dB, aplica una mediana 3×3, lo agrega por municipio y escribe `data/processed/nisar_municipios.csv`. Por defecto borra el HDF5 al terminar. `--conservar` lo deja en `data/raw/nisar/`.

Después hay que volver a lanzar `pipeline` (la caché de lo demás evita repetir Sentinel-1) o, si el CSV ya está, el visor lo verá en cuanto el GeoJSON tenga la columna `vh_db_nisar`. El pipeline, si encuentra el CSV de una pasada anterior, lo une solo.

Sin token, el pipeline no se detiene. El manifiesto lo dice y el combustible del índice es Sentinel-1.

## 4. Visor

```bash
streamlit run app/visor.py
```

Abre `http://localhost:8501`. Lee el GeoJSON procesado. Mover un peso no relanza descargas.

## 5. Tests

```bash
pytest
```

No llaman a la red. El lector NISAR se prueba con un HDF5 sintético en un directorio temporal.

## 6. Si una fuente falla a medias

Mira `data/processed/manifiesto.json`, clave `fases`. Una fase con `"ok": false` trae el error. Las columnas de esa fase quedan vacías en el GeoJSON y la prioridad se recalcula sin ellas. No busques un valor “de relleno”: si no está, es que no se midió.
