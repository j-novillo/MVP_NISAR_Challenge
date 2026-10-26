# Fase 2. SAR

Dos caminos, y solo uno entra en el índice.

1. **Sentinel-1 RTC**, verano de 2024, mediana de VH y de VH−VV por municipio. Es COMB. Lo ejecuta `calcular_sentinel1` dentro del `pipeline`. Descripción completa en `docs/datos_satelite_sar.md` y ficha en `docs/fuentes/sentinel1.md`.
2. **NISAR L2 GCOV.** `buscar_nisar` siempre (CMR público). `procesar_nisar` solo si existe `EARTHDATA_TOKEN`. El resultado, si llega, es la columna `vh_db_nisar` y no sustituye a COMB salvo que alguien active el interruptor del visor.

WorldCover se calcula en esta misma zona del pipeline como contexto (`frac_forestal`) y no como componente.

Si Sentinel-1 no devuelve ninguna escena válida, COMB queda vacío. No se copia el FWI ni el historial en su lugar.
