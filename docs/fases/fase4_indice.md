# Fase 4. Índice y ficheros

Cuando las fases han terminado (o han dejado el hueco anotado):

1. `construir_componentes` crea `comb`, `hist`, `fwi`, `expo`, `acces` en 0–1.
2. `calcular_prioridad` con el preset `equilibrado` crea `prioridad` (0–100) y `factor_dominante`.
3. Se rellenan las columnas `fuente_*` con el nombre real de la fuente o con `no-disponible`.
4. `_escribir` simplifica la geometría a 80 m, guarda el GeoPackage en EPSG:25830, el GeoJSON en EPSG:4326 y el CSV sin geometría.

Los pesos y el significado de cada uno están en `docs/indice_y_pesos.md`. El visor no lee la prioridad como un dato congelado para el mapa interactivo: la vuelve a calcular. La columna `prioridad` del fichero es la del preset equilibrado, útil para abrir la tabla en un SIG sin lanzar Streamlit.
