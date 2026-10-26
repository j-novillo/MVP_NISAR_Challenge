# NISAR L2 GCOV

El método (estructura del HDF5, banda L frente a S, por qué no entra en la validación) está en `docs/datos_satelite_sar.md`, secciones 3, 5 y 9. Esta ficha es la operativa.

| | |
|---|---|
| Producto | Geocoded Polarimetric Covariance, nivel 2 |
| Colecciones CMR | `NISAR_L2_GCOV_PROVISIONAL_V1`, `NISAR_L2_GCOV_BETA_V1` |
| Búsqueda | Pública. `buscar_nisar` en `sources/nisar.py` |
| Descarga | `asf_search`, `ASFSession.auth_with_token` |
| Secreto | Variable de entorno `EARTHDATA_TOKEN`. Plantilla en `.env.example`. Nunca en el repo. |
| Salida de la búsqueda | `data/processed/nisar_escenas_galicia.json` |
| Salida del procesado | `data/processed/nisar_municipios.csv` (`vh_db_nisar`) |

Comandos:

```bash
python -m prioridad_galicia.cli nisar-buscar
EARTHDATA_TOKEN=... python -m prioridad_galicia.cli nisar-procesar --max-escenas 2
```

El procesado elige primero gránulos provisionales cuyo nombre indica canal cruzado, descarga el HDF5 a `data/raw/nisar/`, lee HVHV de la frecuencia A, convierte a dB, mediana 3×3, zonal en EPSG:25830, y borra el HDF5 si no se pasó `--conservar`.

Sin token, o si el token es rechazado, el pipeline no se cae. `fuente_combustible` sigue siendo `sentinel-1-rtc` y el visor no enseña el interruptor de NISAR.

El lector se prueba sin red en `tests/test_nisar_y_geo.py` con un HDF5 de juguete: tiene que preferir el HV de la banda L y respetar el EPSG que el fichero declara, no uno supuesto.
