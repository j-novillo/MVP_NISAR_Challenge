# Limitaciones

Están escritas para decirlas en voz alta, no para esconderlas en un anexo.

| Límite | Qué implica aquí |
|---|---|
| Las ocho escenas NISAR procesadas son del 13 al 20 de octubre de 2026. | Van después de la validación. El índice por defecto sigue en Sentinel-1 de 2024. El HV (313 municipios, −19,7 a −10,3 dB, r = 0,57 con el VH de banda C) se mira en el visor, con el interruptor apagado al entrar. |
| La banda C satura en masas densas. | VH ordena municipios, no pesa toneladas. Dos concellos de eucalipto adulto pueden salir parecidos aunque uno tenga más biomasa de la que la banda C distingue. La banda L, cuando haya un verano entero anterior a la campaña, es la que afloja ese tope. |
| El SAR del índice está agregado a 400 m y con pocas fechas. | Speckle y ángulo de incidencia se diluyen en la mediana municipal. Se pierde el variation dentro del concello: este mapa no dice en qué ladera desbrozar. |
| Mezcla de órbitas ascendente y descendente. | La mediana no está hecha sobre una sola geometría de incidencia. Es más estable para un proxy y menos limpia para una inversión biofísica. |
| Sin máscara forestal dentro de COMB. | Un VH alto puede ser monte o un polígono industrial. El ratio VH/VV y la fracción WorldCover de la ficha están para leerlo; no eliminan el caso. |
| Incendib en pausa y EGIF sin volcado municipal abierto. | HIST es EFFIS 2010–2024, no la estadística oficial de causas, medios y tiempos. Esos campos del parte (más de cien) no están. |
| EFFIS y el parte de la Xunta no miden igual. | La validación puede moverse si se repitiera con los perímetros del PLADIGA. No se ha hecho porque ese cruce no estaba en un fichero abierto usable a escala municipal para todo el periodo. |
| FWI de seis días de 2024, no un clima de 30 años ni el pronóstico de hoy. | Describe la campaña previa. Un operativo diario debe seguir usando el visor de EFFIS. |
| Parques de bomberos de OSM y distancia en línea recta. | Faltan bases que nadie ha mapeado, sobra alguna etiqueta equivocada, y un estuario cuenta como si se cruzara volando. No es el tiempo de llegada del PLADIGA. |
| Población sin interfaz urbano-forestal explícita. | La exposición es censo y densidad. No hay edificaciones ni perímetro de núcleo del IGN en la fórmula. |
| Pesos de experto, no ajustados por máxima verosimilitud. | Se pueden mover. La validación dice si el movimiento concentra mejor las hectáreas; no convierte el índice en un modelo de ignición. |
| Municipios costeros y muy pequeños. | `all_touched` evita que desaparezcan de la zonal, a costa de mezclar algún píxel de borde. |

El cultivo útil de estas limitaciones, el del enunciado, se mantiene: es una herramienta de **prevención y priorización**, complementaria de FIRMS y de EFFIS en lo operativo, con el procesado SAR reducido a productos ya corregidos (RTC, GCOV) y a una mediana.
