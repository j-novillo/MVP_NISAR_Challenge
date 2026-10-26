# Territorio: municipios del IGN

Unidad espacial del MVP: el municipio, en las cuatro provincias de Galicia (A Coruña 15, Lugo 27, Ourense 32, Pontevedra 36).

## De dónde sale

Servicio WFS INSPIRE del Instituto Geográfico Nacional:

`https://www.ign.es/wfs-inspire/unidades-administrativas`

Tipo de entidad: `au:AdministrativeUnit`. El servicio no ofrece `application/json`; sí `application/geo+json`. El recuadro se pide en orden latitud/longitud con el URN `urn:ogc:def:crs:EPSG::4326`, y la geometría en EPSG:4258 (ETRS89 geográfico). Lo hace `cargar_municipios` en `sources/territorio.py`, paginando con `count=100` y `startIndex`.

## Filtro

El WFS, en ese recuadro, devuelve también provincias y otros niveles. Se conservan solo las entidades cuyo `nationalLevel` contiene `4thOrder` (municipio en la jerarquía INSPIRE española) y cuyo `nationalCode` termina en un código INE de cinco dígitos de esas cuatro provincias.

El código nacional del IGN tiene más dígitos (por ejemplo `34123232011` para Beariz). Los cinco últimos son el INE (`32011`). El nombre se saca del endónimo (`GeographicalName` / `text`). Si el mismo código aparece dos veces, se queda la geometría de mayor área.

## Proyección y área

Se reproyecta a EPSG:25830 y se calcula `area_ha` con el área plana de esa proyección. Las geometrías inválidas pasan por `make_valid`. Para el fichero de salida se simplifican a 80 m (`pipeline._escribir`) para que el GeoJSON sea ligero; el cálculo zonal usa la geometría sin esa simplificación de salida, leída de la caché `data/cache/municipios_25830.gpkg`.

## Qué no se usa

El GeoJSON de concellos de la Consellería de Sanidade y el servicio de la IDE de Galicia responden y son oficiales a su manera, pero el enunciado pide el límite del IGN y el WFS lo da sin registro. No se mezclan las dos geometrías.
