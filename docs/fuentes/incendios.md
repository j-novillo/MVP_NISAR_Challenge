# Incendios: historial y validación

El índice necesita dos cosas distintas y no se pueden mezclar.

- **Historial (HIST).** Lo que ya ardió antes de la campaña que se quiere anticipar. Entra en la fórmula.
- **Validación.** Lo que ardió en 2025 y 2026. No entra en la fórmula. Sirve para preguntar si el índice, construido sin esos años, concentraba ahí las hectáreas.

## Lo que se intentó y no sirvió como serie municipal

`intentar_fuentes_bloqueadas` (en `sources/incendios.py`) deja constancia en el manifiesto, sin fabricar filas.

| Fuente | Qué pasó |
|---|---|
| [Incendib](https://incendib.es/) | El sitio anuncia una pausa. No hay CSV ni GeoJSON que descargar. Era el atajo del enunciado a la EGIF. |
| EGIF (MITECO) | El buscador público exporta Excel o XML de los partes ya consolidados, provincia a provincia, con formulario. No hay un volcado abierto y estable por municipio para toda Galicia que se pueda pedir por URL. |
| Xunta / IGE, datos abiertos | Hay un CSV municipal, pero solo de 2001 a 2006. Desde 2007 la serie abierta es por distrito forestal, no por concello. Unir 2001–2006 con otra definición a partir de 2010 cambiaría el significado de HIST a mitad de la serie, así que **no se usa en el índice**. El intento de descarga queda anotado. |

## Lo que sí entra: EFFIS

API, sin clave:

`https://api.effis.emergency.copernicus.eu/rest/2/burntareas/current/`

Filtros que acepta y que se probaron: `province` con los nombres `A Coruña`, `Lugo`, `Ourense` y `Pontevedra` (las formas `Coruña` y `Orense` devuelven cero), y `firedate__gte` / `firedate__lte` con fecha y hora. Se pagina con `limit=200` hasta que `next` viene vacío. Se deduplica por `id`.

Cada registro trae el perímetro en GeoJSON (`shape`), la fecha, el área que publica EFFIS y el municipio según su propia etiqueta. **No se usa esa etiqueta para agregar.** El nombre de EFFIS no coincide siempre con el del IGN. La hectárea del municipio es el área de la intersección del perímetro con el término, en EPSG:25830, después de simplificar ambos a 40 m para que el cruce sea tratable. Un fuego que cruza dos concellos reparte la superficie. `n_incendios_*` cuenta perímetros distintos que tocan el término, no la etiqueta de EFFIS.

| Columna | Ventana | Uso |
|---|---|---|
| `n_incendios_hist`, `ha_quemadas_hist`, `ha_quemadas_1000ha_hist` | 2010-01-01 a 2024-12-31 | Componente HIST |
| `n_incendios_val`, `ha_quemadas_val` | 2025-01-01 a 2026-12-31 | Solo validación |

EFFIS cartografía área quemada a partir de MODIS, VIIRS (los mismos sensores que NASA FIRMS) y Sentinel-2. El CSV en tiempo casi real de FIRMS pide una `MAP_KEY` que no está en el entorno y no se ha inventado. La validación usa el perímetro, que es más adecuado para hectáreas que el foco activo.

Un municipio sin intersección se queda en cero **porque la descarga de esa ventana terminó bien**. Si la fase entera falla, las columnas no se crean y el índice las trata como hueco, no como “aquí no ardió”.
