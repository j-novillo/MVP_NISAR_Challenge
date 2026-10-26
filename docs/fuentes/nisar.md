# NISAR L2 GCOV

El método (estructura del HDF5, banda L frente a S, por qué no entra en la validación) está en `docs/datos_satelite_sar.md`, secciones 3, 5 y 9. Esta ficha es la operativa.

| | |
|---|---|
| Producto | Geocoded Polarimetric Covariance, nivel 2 |
| Colecciones CMR | `NISAR_L2_GCOV_PROVISIONAL_V1`, `NISAR_L2_GCOV_BETA_V1` |
| Búsqueda | Pública. `buscar_nisar` en `sources/nisar.py` |
| Descarga | `GET` del `url_h5` del CMR con `Authorization: Bearer`. No `ASFSession.auth_with_token`. |
| Secreto | Variable de entorno `EARTHDATA_TOKEN`. Plantilla en `.env.example`. Nunca en el repo. |
| Salida de la búsqueda | `data/processed/nisar_escenas_galicia.json` |
| Salida del procesado | `data/processed/nisar_municipios.csv` y `data/processed/nisar_lectura.json` |

Comandos:

```bash
python -m prioridad_galicia.cli nisar-buscar
EARTHDATA_TOKEN=... python -m prioridad_galicia.cli nisar-procesar --max-escenas 8 --escenas PREFIJO_DEL_TITULO
```

## Por qué Bearer y no la sesión de ASF

La cuenta con la que se descargaron las escenas de este repositorio **aún no ha aceptado la EULA de la aplicación de ASF**. `ASFSession.auth_with_token` responde 403 «EULA Acceptance Failure» aunque el token de Earthdata sea válido. El enlace HTTPS que CMR ya publica (`url_h5`, en `nisar.asf.earthdatacloud.nasa.gov`) acepta el mismo token como Bearer y completa la redirección a la URL firmada. Hasta que esa EULA se acepte en Earthdata, este es el camino que funciona. El token no se escribe en el código ni en el manifiesto.

## Qué hay procesado

Ocho gránulos GCOV provisionales, HVHV de banda L, del 13, 18 y 20 de octubre de 2026. El detalle de cada lectura (EPSG 32629 o 32630, stride 10, paso 20 m, municipios cubiertos al 50 %) está en `nisar_lectura.json`. Dos de esas escenas no cubren al 50 % ningún municipio: entran en la lectura y no aportan a la mediana.

La combinación es municipal, no un mosaico previo: mediana zonal de cada escena, se descarta si cubre menos del 50 % de los píxeles del municipio, y `vh_db_nisar` es la mediana de las que quedan. Los píxeles por debajo de −50 dB se tratan como sin dato antes de agregar.

Cobertura de esa pasada: **313 de 313** municipios, HV entre **−19,7 y −10,3 dB**. La correlación de Pearson con el VH de Sentinel-1 (verano 2024) es **r = 0,57**.

## Por qué no entra en el índice por defecto

Esas fechas son posteriores a casi toda la ventana de validación (incendios EFFIS de 2025 y 2026). El HV de octubre de 2026 ya puede incluir el efecto del fuego que se pretende haber anticipado. El índice por defecto sigue en Sentinel-1 de 2024. El visor enseña el interruptor, apagado, para mirar la banda L sabiendo que esa vista ya no es retrospectiva.

Sin token, el pipeline no se cae. Si el CSV zonal ya está en `data/processed/`, el pipeline lo une y el interruptor aparece igual.

El lector se prueba sin red en `tests/test_nisar_y_geo.py` con un HDF5 de juguete: tiene que preferir el HV de la banda L, respetar el EPSG que el fichero declara (atributo del grupo o `epsg_code` de `projection`) y anular el relleno por debajo de −50 dB.
