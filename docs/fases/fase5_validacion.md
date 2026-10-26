# Fase 5. Validación

`evaluar` (`validation.py`) ordena los municipios por la prioridad del preset equilibrado y mide:

- Qué fracción de las hectáreas EFFIS 2025–2026 cae en el 10 %, el 20 % y el 30 % de municipios con más prioridad. El azar, si las hectáreas no tuvieran que ver con el índice, dejaría aproximadamente esa misma fracción.
- El AUC de la pregunta binaria “el municipio tiene alguna hectárea en el cruce”. No distingue un conato de un gran incendio; para eso está la captura de hectáreas.
- La suma y la media de hectáreas por quintil de prioridad. `figura_quintiles` lo dibuja y el pipeline lo guarda en `data/processed/validacion_quintiles.png`. El visor redibuja el mismo gráfico con los pesos de la pantalla.

El método, las cautelas y cómo leer un resultado bueno o flojo están en `docs/validacion.md`.

No hay un modelo que ajustar. Si el gráfico no concentra hectáreas en Q5, el índice no “se entrena”: se cambia un peso en el visor y se vuelve a mirar, o se reconoce el límite en `docs/limitaciones.md`.
