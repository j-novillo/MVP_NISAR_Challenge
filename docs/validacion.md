# Validación retrospectiva

La pregunta del MVP es concreta: **¿los municipios que más ardieron en 2025 y 2026 estaban ya arriba en un índice construido sin esos incendios?**

## Diseño temporal

| Pieza | Cuándo | Por qué |
|---|---|---|
| Sentinel-1 (COMB) | Verano 2024 | Estado del combustible antes de las dos campañas que se evalúan. |
| Historial (HIST) | Perímetros EFFIS 2010–2024 | El antecedente, sin colar el resultado. |
| FWI | Seis fechas del verano 2024 | Carácter meteorológico conocido de antemano, no el parte del día del incendio. |
| Población | Padrón (año que publique el INE; en la ejecución de referencia, 2025) | Cambia poco de un año a otro. No es un resultado del fuego. |
| OSM | El extracto del servidor el día de la descarga | Tampoco es un resultado del fuego. |
| Objetivo | Hectáreas EFFIS 2025-01-01 a 2026-12-31, intersección con el municipio | Lo que se quiere haber señalado. |

NISAR no entra. Su archivo sobre Galicia, en el catálogo CMR, es de 2026.

## Métricas

Están implementadas en `validation.py` y no dependen de scikit-learn.

**Captura.** Se ordenan los municipios de más a menos prioridad. “Top 10 %” es el techo del 10 % de la lista (al menos un municipio). Se suma `ha_quemadas_val` dentro de ese grupo y se divide por el total de hectáreas del cruce. El azar, si el índice no informara, anda por el propio 10 %. Una captura del 40 % en el top 10 % es cuatro veces el azar: el índice está agrupando el daño. Una captura del 10 % es no haber dicho nada.

**AUC.** Clase positiva: el municipio tiene alguna hectárea en 2025–2026. Es un complemento, porque trata igual 2 ha que 2 000. Sale `None` si todos ardieron o si no ardió ninguno.

**Quintiles.** `qcut` en cinco grupos de prioridad. El gráfico (`figura_quintiles`) pone las hectáreas de cada grupo. Lo que se espera de un índice útil es una barra que crece hacia Q5. Una barra alta en Q1 es un fallo visible: ahí ardieron sitios que el índice daba por tranquilos.

El visor repite las tres cuentas con los pesos que haya en pantalla, así se puede ver si el preset de bombero concentra mejor o peor que el forestal. El PNG y el JSON guardados por el pipeline corresponden solo al preset equilibrado.

## Cómo no leerlo

- No es una validación de NISAR. La banda L no está en el índice que se evalúa.
- No es una validación píxel a píxel del SAR. Se evalúa el índice municipal entero, historial incluido. Un COMB malo puede quedar tapado por un HIST bueno, y al revés. El factor dominante y los deslizadores sirven para separar esas historias.
- EFFIS no es la estadística oficial de la Xunta. Un perímetro pequeño puede no estar, y uno grande puede diferir del parte de superficie. Es la fuente espacial abierta y coherente en los dos periodos; la cautela va en `docs/limitaciones.md`.
- Un AUC alto con poca superficie en el top 10 % significa que el índice acierta “dónde hubo algo”, no “dónde estuvo el daño”. Para prevención de grandes incendios manda la captura de hectáreas.
