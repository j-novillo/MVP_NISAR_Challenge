# Fase 3. Variables auxiliares

Corren antes del SAR en el código (`pipeline.py`) porque no dependen de él, pero conceptualmente son esta fase:

| Variable | Módulo | Documento |
|---|---|---|
| Historial 2010–2024 y validación 2025–2026 | `sources/incendios.py` | `docs/fuentes/incendios.md` |
| FWI medio del verano 2024 | `sources/fwi.py` | `docs/fuentes/fwi.md` |
| Población y densidad | `sources/poblacion.py` | `docs/fuentes/poblacion.md` |
| Distancia al parque y densidad viaria | `sources/osm.py` | `docs/fuentes/osm.md` |

Cada una tiene su propio `try` en `_fase`. El fallo de Overpass no borra el padrón, y al revés.
