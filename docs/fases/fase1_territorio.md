# Fase 1. Territorio

`cargar_municipios` descarga el WFS del IGN, filtra los municipios gallegos y los deja en EPSG:25830 con `codigo_ine`, `nombre`, `provincia` y `area_ha`.

Si esta fase falla, el pipeline se detiene: sin geometría no hay índice. El resto de las fases toleran el fallo. El detalle del filtro está en `docs/fuentes/territorio.md`.

Caché: `data/cache/municipios_25830.gpkg`. `--forzar` la rehace.
