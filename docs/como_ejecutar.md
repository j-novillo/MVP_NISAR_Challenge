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
| `data/processed/nisar_municipios.csv` | HV municipal de las ocho escenas de octubre de 2026. |
| `data/processed/nisar_lectura.json` | Qué escena se leyó, su EPSG y cuántos municipios cubrió al 50 %. |
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
python -m prioridad_galicia.cli nisar-procesar --max-escenas 8 --escenas PREFIJO_DEL_TITULO
```

También vale un `.env` en la raíz (está en `.gitignore`; la plantilla es `.env.example`):

```bash
cp .env.example .env
# edita EARTHDATA_TOKEN
python -m prioridad_galicia.cli nisar-procesar --max-escenas 2
```

`ASFSession.auth_with_token` no se usa. En la cuenta que procesó las escenas de este repositorio esa llamada devuelve 403 porque **la EULA de la aplicación de ASF todavía no está aceptada**. La descarga va en Bearer directo contra el `url_h5` del CMR. El detalle está en `docs/fuentes/nisar.md`.

El procesado lee el HV de banda L, anula el relleno por debajo de −50 dB, aplica una mediana 3×3 y combina por municipio: una escena solo cuenta si cubre al menos el 50 % de los píxeles, y el valor publicado es la mediana de esas escenas. Escribe `nisar_municipios.csv` y `nisar_lectura.json`. Por defecto borra el HDF5. `--conservar` lo deja en `data/raw/nisar/`.

En este repositorio esa pasada ya está hecha (ocho escenas del 13, 18 y 20 de octubre de 2026, 313 municipios, HV de −19,7 a −10,3 dB, correlación 0,57 con el VH de Sentinel-1). El GeoJSON del índice ya lleva `vh_db_nisar`, así que el visor enseña el interruptor sin repetir la descarga. El pipeline, si encuentra el CSV de una pasada anterior y no hay token, lo une solo.

Sin token y sin ese CSV, el pipeline no se detiene. El manifiesto lo dice y el combustible del índice es Sentinel-1. Con CSV o sin él, NISAR no entra en el índice por defecto: las escenas son de octubre de 2026, posteriores a la validación.

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
