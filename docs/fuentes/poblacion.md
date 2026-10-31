# Población: padrón del INE

Fuente: operación “Cifras oficiales de población de los municipios españoles” (DPOP), API JSON del INE, último periodo publicado (`nult=1`).

Tablas provinciales, porque la tabla nacional es enorme y estas cuatro bastan:

| Provincia | Id de tabla |
|---|---|
| A Coruña | 2868 |
| Lugo | 2880 |
| Ourense | 2885 |
| Pontevedra | 2890 |

URL: `https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{id}?nult=1`. La llama `descargar_padron` en `sources/poblacion.py`.

## Cruce con el municipio del IGN

La serie no trae el código INE. El nombre viene como `Abegondo. Total. Total habitantes. Personas.` y, en los que llevan artículo, al estilo del nomenclátor: `Coruña, A`. El IGN dice `A Coruña`.

`variantes_toponimo` genera las dos órdenes del artículo (gallego y castellano: a, o, as, os, el, la, los, las) y quita acentos. Dentro de la provincia se elige el cruce cuya variante común es más larga, y los nombres largos eligen antes, para que “A Estrada” no se quede sin ficha porque “Estrada” ya consumió el registro. El tests `test_toponimos_con_articulo` cubre A Coruña y O Irixo.

Cada tabla incluye también el total provincial, con el mismo aspecto de serie. Es el valor más alto de la tabla (la suma de los concellos) y se descarta. Así el municipio de Pontevedra no se confunde con la provincia de Pontevedra: el total provincial es estrictamente mayor.

## Columnas

- `poblacion`: personas del último año que devolvió la API (el campo `Anyo` de la serie; en la ejecución de referencia, 2025).
- `anio_poblacion`: ese año.
- `densidad_hab_km2`: población / (área en ha / 100).

Tres términos no cruzan por el nombre porque el IGN mantiene el topónimo tradicional y el padrón el oficial vigente. Se unen por el código INE de la geometría, no por similitud difusa:

| Código | Nombre en el IGN | Nombre en el padrón |
|---|---|---|
| 27002 | Alfoz do Castrodouro | Alfoz |
| 32023 | O Castro de Caldelas | Castro Caldelas |
| 36008 | Cangas de Morrazo | Cangas |

El diccionario está en `ALIAS_POR_CODIGO` y no se aplica a ningún otro municipio. Quien siga sin cruce se queda sin población. La lista va en el manifiesto (`municipios_sin_poblacion`). No se copia la media de la provincia.
