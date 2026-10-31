# Fase 0. Entorno

No hay cuentas que activar para el camino por defecto.

- Python 3.11+ y el `requirements.txt` de la raíz. Incluye `geopandas`, `rasterio`, `rioxarray` (disponible para un análisis interactivo de un ráster ya recortado; el pipeline lee los COG con `rasterio` porque la ventana y el overview se controlan mejor así), `pystac-client`, `planetary-computer`, `asf-search`, `h5py` y `streamlit`.
- Sistema de referencia único: EPSG:25830. Constantes en `config.py`.
- Google Earth Engine no se usa. Sentinel-1 llega por Planetary Computer.
- NISAR es opcional y posterior. El token, si se va a procesar, se exporta como `EARTHDATA_TOKEN` (ver `docs/como_ejecutar.md`). Sin él, la fase de búsqueda CMR sí corre.

El comando único de las fases 1 a 5 es:

```bash
python -m prioridad_galicia.cli pipeline
```
