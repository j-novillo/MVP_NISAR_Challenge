# Índice y pesos

Para cada municipio *i*:

\[
P_i = 100 \cdot (w_1 \mathrm{COMB}_i + w_2 \mathrm{HIST}_i + w_3 \mathrm{FWI}_i + w_4 \mathrm{EXPO}_i + w_5 \mathrm{ACCES}_i)
\]

Los cinco componentes están en 0–1. Los pesos que llegan a la fórmula suman 1. Si el usuario (o un hueco de datos) deja un componente fuera, `calcular_prioridad` reparte el peso de ese componente entre los que sí tienen valor **en ese municipio**. No se rellena con la media de Galicia ni con cero.

Implementación: `construir_componentes` y `calcular_prioridad` en `src/prioridad_galicia/index.py`. Los números viven en `src/prioridad_galicia/config.py` (`PRESETS`, `PESOS_COMB`, `PESOS_HIST`, `PESOS_EXPO`, `PESOS_ACCES`) para que el visor, el pipeline y los tests no diverjan.

## Cómo se fabrica cada componente

La normalización externa es `robust_minmax`: percentil 5 a percentil 95, recorte a [0, 1]. Así un solo municipio extremo no aplasta al resto.

### COMB, combustible SAR

\[
\mathrm{COMB} = 0{,}55 \cdot \mathrm{norm}(\mathrm{VH_{dB}}) + 0{,}45 \cdot \mathrm{norm}(\mathrm{VH_{dB}}-\mathrm{VV_{dB}})
\]

- El 55 % es la retrodispersión cruzada. En banda C, VH crece con el volumen de hojas y ramas finas hasta saturar. Es el término más directo de “hay estructura vegetal”.
- El 45 % es el ratio, en decibelios. Resta el brillo que comparten VH y VV (humedad superficial, ángulo de incidencia residual) y penaliza el urbano, donde VV se dispara por el doble rebote. Sin este término, las ciudades grandes competirían con el monte.
- No entra la fracción de WorldCover. Esa capa se enseña en la ficha (`frac_forestal`) para leer el número, pero meterla en COMB mezclaría un mapa de ocupación del suelo de 2021 con la medida SAR y rompería la lectura “esto es radar”.
- No entra NISAR. Las ocho escenas GCOV agregadas son del 13 al 20 de octubre de 2026. El HV municipal (313/313, de −19,7 a −10,3 dB) correlaciona r = 0,57 con el VH de Sentinel-1, pero esa fecha es posterior a los incendios de la validación. Sustituirlo en COMB haría que el índice viera el monte ya quemado. El visor lo deja en un interruptor, apagado por defecto.

Pesos 55/45 y no 50/50 porque, si el ratio falla en una escena, el canal que el reto pide mostrar es el de volumen. El reparto interno está en `PESOS_COMB`.

### HIST, historial

\[
\mathrm{HIST} = 0{,}45 \cdot \mathrm{norm}(\log(1+n)) + 0{,}55 \cdot \mathrm{norm}(\log(1+\mathrm{ha}/1000\,\mathrm{ha}))
\]

*n* es el número de perímetros EFFIS de 2010 a 2024 que tocan el municipio. Las hectáreas son las de la intersección real con el término municipal, no el área entera del perímetro cuando el fuego cruza un límite, y se expresan por cada 1000 ha de municipio para no premiar solo a los concellos grandes.

El logaritmo existe porque Ourense y el sur de Pontevedra tienen colas muy largas: sin él, dos o tres municipios fijarían el 1 y el resto quedaría en cero. El 55 % va a la superficie y no al recuento porque un conato y un gran incendio no son el mismo antecedente para quien planifica fajas. Los años 2025 y 2026 no entran aquí: son la validación.

### FWI, peligro meteorológico

\(\mathrm{FWI} = \mathrm{norm}(\text{media de la capa EFFIS mf010.fwi})\).

Fechas fijas del verano de 2024 (15 de junio, 1 y 15 de julio, 1 y 15 de agosto, 1 de septiembre), anteriores a la validación. No es el pronóstico de mañana: es el carácter meteorológico de la campaña previa, que es lo que un índice anual puede conocer antes de que empiece la siguiente. El FWI canadiense junta sequedad del combustible fino, del duff y el viento; EFFIS lo calcula a partir de modelos ECMWF / Météo-France y lo publica ya clasificado en esa capa. Más FWI, más prioridad.

### EXPO, exposición

\[
\mathrm{EXPO} = 0{,}60 \cdot \mathrm{norm}(\log(1+\mathrm{población})) + 0{,}40 \cdot \mathrm{norm}(\mathrm{densidad})
\]

La población es el padrón del INE (personas). El logaritmo evita que Vigo y A Coruña se lleven solas el componente. La densidad (hab/km² sobre el área del término en EPSG:25830) sube a los núcleos compactos frente al municipio extenso con la misma población dispersa. No hay una capa nacional abierta de interfaz urbano-forestal a escala de municipio; la densidad más el censo es el proxy, y la ficha lo dice con los números crudos al lado. WorldCover enseña cuánto del término es bosque, para leer el contacto a ojo, sin meterlo en la fórmula.

### ACCES, dificultad de llegada

\[
\mathrm{ACCES} = 0{,}65 \cdot \mathrm{norm}(d) + 0{,}35 \cdot \mathrm{norm}\!\left(\frac{1}{d_v + 0{,}05}\right)
\]

*d* es la distancia en línea recta, en kilómetros, desde un punto interior del municipio (`representative_point`) al `amenity=fire_station` de OpenStreetMap más cercano. No es un tiempo de recorrido: no hay grafo de velocidades ni el parque de bomberos de OSM es la lista oficial de bases de la Xunta. Es el proxy que el propio enunciado admite mientras no exista un inventario nacional de brigadas.

*d_v* es la densidad de autovía, vía troncal, primaria y secundaria (km de eje por km²). El 0,05 del denominador evita el infinito en un municipio sin esas vías. Se normaliza la inversa: poca red, más prioridad. El 65 % es la distancia al parque porque es lo que más se parece a “¿llega alguien?”. El 35 % es la red, que condiciona tanto la extinción como la evacuación.

ACCES alto significa **peor** acceso. En el índice, peor acceso sube la prioridad. Quien quiera el criterio contrario (actuar solo donde el medio entra fácil) baja este peso en el visor a cero.

## Presets

Están en `PRESETS`. El pipeline guarda el equilibrado. El visor parte de él y deja mover cada peso; los que se aplican son los de la pantalla renormalizados a 1.

| Preset | COMB | HIST | FWI | EXPO | ACCES | Para quién |
|---|---:|---:|---:|---:|---:|---|
| Equilibrado | 0,30 | 0,25 | 0,20 | 0,15 | 0,10 | Quien planifica la campaña anual. El 55 % es lo que se puede tratar (combustible e historial). El 20 % es la urgencia meteorológica. El 25 % restante mira a las personas y a si se llega. |
| Bombero | 0,15 | 0,20 | 0,25 | 0,15 | 0,25 | Quien despliega medios. La mitad del índice es “¿el día es extremo y el parque queda lejos?”. El combustible contextualiza, no decide el relevo. |
| Forestal | 0,40 | 0,30 | 0,15 | 0,05 | 0,10 | Quien diseña desbroces, quemas prescritas y fajas. El 70 % es estructura vegetal y recurrencia. La población es un condicionante, no el objetivo. |
| Protección civil | 0,10 | 0,15 | 0,25 | 0,35 | 0,15 | Quien prioriza vidas y núcleos. Exposición y FWI suman el 60 %. El acceso pesa porque condiciona la evacuación, no porque el monte esté lejos de un retén. |

## Factor dominante

`factor_dominante` es el componente cuyo producto (valor 0–1 × peso) es el mayor en ese municipio. Sirve para la frase del ranking: no dice “este concello es peligroso” a secas, dice si manda el monte, el historial, el tiempo, la gente o el aislamiento. Si falta un componente, no compite.

## Lo que el índice no es

No es una probabilidad de ignición. No es el número de hectáreas que arderán. No sustituye al FWI del día ni a FIRMS cuando el incendio ya está activo. Ordena términos municipales para decidir **dónde actuar antes** de la campaña, con las cuentas a la vista.
