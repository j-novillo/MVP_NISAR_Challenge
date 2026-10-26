# Sentinel-1 RTC

El detalle físico (gamma0, dB, speckle, COG) está en `docs/datos_satelite_sar.md`. Aquí queda la ficha operativa de la fuente.

| | |
|---|---|
| Colección STAC | `sentinel-1-rtc` |
| Catálogo | `https://planetarycomputer.microsoft.com/api/stac/v1` |
| Cuenta | Ninguna. `planetary_computer.sign` añade una firma SAS de corta duración a la URL del blob. |
| Bandas | `vh` y `vv`, GeoTIFF COG, gamma0 en potencia lineal, nodata −32768, 10 m |
| Ventana | 2024-06-01 a 2024-09-15 (`S1_INICIO`, `S1_FIN`) |
| Resolución de trabajo | 400 m por defecto (`--resolucion`) |
| Código | `sources/sentinel1.py`, función `calcular_sentinel1` |

Una escena completa ronda 1,8 GB por polarización. `leer_banda_decimada` pide solo la ventana de Galicia, diezmada. El entorno GDAL (`_entorno_gdal`) fuerza lectura perezosa del COG (`GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR`, fusión de rangos HTTP, caché VSI).

Columnas que salen: `vh_db`, `ratio_vh_vv_db`, `n_obs_sar`.

Si ninguna escena se puede leer, las tres quedan vacías, COMB queda vacío y el índice sigue con el resto de componentes. El manifiesto lista `escenas_usadas` y `errores` con el identificador STAC.
