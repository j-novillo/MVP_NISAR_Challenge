# Fase 2. SAR

Dos caminos, y solo uno entra en el índice.

1. **Sentinel-1 RTC**, verano de 2024, mediana de VH y de VH−VV por municipio. Es COMB. Lo ejecuta `calcular_sentinel1` dentro del `pipeline`. Descripción completa en `docs/datos_satelite_sar.md` y ficha en `docs/fuentes/sentinel1.md`.
2. **NISAR L2 GCOV.** `buscar_nisar` siempre (CMR público). `procesar_nisar` solo si existe `EARTHDATA_TOKEN`; si no, y ya hay `nisar_municipios.csv`, se une ese CSV. La pasada incluida usa ocho escenas de octubre de 2026 (HV de −19,7 a −10,3 dB en los 313 municipios, r = 0,57 con Sentinel-1). `vh_db_nisar` no sustituye a COMB: esas fechas son posteriores a la validación. El visor lo ofrece con un interruptor.

WorldCover se calcula en esta misma zona del pipeline como contexto (`frac_forestal`) y no como componente.

Si Sentinel-1 no devuelve ninguna escena válida, COMB queda vacío. No se copia el FWI ni el historial en su lugar.
