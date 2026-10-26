# Visor

Aplicación Streamlit en `app/visor.py`. Se arranca con:

```bash
streamlit run app/visor.py
```

Lee `data/processed/municipios_indice.geojson`. Si no está, lo dice y no inventa un mapa de ejemplo.

## Qué se ve

- **Mapa coroplético.** Folium sobre el lienzo gris claro de Esri (teselas públicas, sin clave; CartoDB Positron pide API key y marca la tesela), color `YlOrRd` de 0 a 100, tooltip con municipio, provincia, prioridad y factor dominante. El gris del polígono, no el del fondo, es un municipio sin prioridad (todos sus componentes vacíos).
- **Top 10.** Los diez valores más altos con el factor que manda.
- **Ficha.** Selector de municipio (y, si el clic del mapa trae `codigo_ine`, ese municipio). Muestra la prioridad, el factor, las hectáreas de validación, una barra con el aporte de cada componente (peso × valor, en puntos) y la tabla de números crudos: dB, observaciones SAR, fracción forestal, incendios, FWI, población, distancia al parque, NISAR si existe.
- **Pesos.** Un preset (equilibrado, bombero, forestal, protección civil) y un deslizador por componente. Lo que se aplica es el vector renormalizado a 1, y esa renormalización se escribe al lado. Cambiar un peso recalcula `calcular_prioridad` en memoria y actualiza mapa, ranking, ficha y gráfico de validación. No toca el GeoJSON del disco.
- **Validación.** Métrica del 10 % de municipios, AUC y barras por quintil, calculadas con los pesos de esa pantalla.
- **Procedencia.** El desplegable final vuelca el manifiesto: fases, coberturas y el comando de NISAR.

## NISAR en la interfaz

El interruptor “Sustituir el combustible por NISAR” solo aparece si `vh_db_nisar` tiene algún valor. Al activarlo, COMB pasa a ser el min-max robusto de ese HV y un aviso dice que la validación deja de ser retrospectiva. Sin la columna, un texto indica que el combustible es Sentinel-1 y remite al comando del README.

## Tema

`.streamlit/config.toml` fija un fondo claro y un acento ocre. No cambia ningún número.
