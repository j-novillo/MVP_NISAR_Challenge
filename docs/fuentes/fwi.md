# Peligro meteorológico: FWI de EFFIS

El Fire Weather Index (FWI) es el índice canadiense de peligro meteorológico de incendio. Junta la humedad del combustible fino (FFMC), la del mantillo (DMC), la sequía profunda (DC), la propagación inicial (ISI) y el combustible disponible (BUI) en un número que sube cuando el día es más fácil de quemar. EFFIS lo calcula sobre modelos meteorológicos y lo publica como capa WMS.

## Cómo se pide

Capa: `mf010.fwi`, en `https://maps.effis.emergency.copernicus.eu/effis`.

`descargar_fwi` (`sources/fwi.py`) hace un `GetMap` WMS 1.1.1 en `image/tiff`, SRS EPSG:4326, sobre el bbox de Galicia, 265×210 píxeles (unos 0,01°). Se probó WMS 1.3.0 y otras capas (`ecmwf007.fwi`, `ecmwf.fwi`): responden con una excepción de capa no definida. `mf010.fwi` en 1.1.1 devuelve un TIFF de una banda, del orden de decenas de kilobytes, con el valor del índice y no una imagen RGB.

Si el TIFF viniera sin georreferencia (origen en el píxel 0,0, un fallo habitual de algunos WMS), se le asigna el bbox que se acaba de pedir. No se recoloca “a ojo” a otra zona.

Valores fuera de [0, 200] pasan a NaN. El FWI operativo rara vez sale de ese rango; un 255 o un nodata no deben entrar en la media.

## Fechas

`FWI_FECHAS` en `config.py`: 2024-06-15, 2024-07-01, 2024-07-15, 2024-08-01, 2024-08-15, 2024-09-01.

Se reproyectan a la rejilla de 1 km en EPSG:25830, se promedian las fechas que respondieron y `estadistica_zonal` con media (no mediana: el FWI ya es un índice suave) da `fwi_medio`. Luego `robust_minmax` lo lleva a 0–1.

Son fechas del verano **anterior** a la validación. Usar el FWI de agosto de 2025 para “explicar” los incendios de agosto de 2025 sería contemporáneo al suceso. Un índice de pretemporada solo puede conocer el carácter meteorológico de campañas pasadas, o el pronóstico del día, que es otra herramienta (EFFIS ya la tiene, a 1–9 días) y no es este mapa anual.

Si una fecha devuelve XML de error, se anota y se sigue con las demás. Si no responde ninguna, `fwi_medio` queda vacío y su peso se reparte.
