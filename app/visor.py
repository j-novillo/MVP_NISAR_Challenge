"""Visor Streamlit: mapa, ranking y ficha con pesos editables."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from branca.colormap import linear
from streamlit_folium import st_folium

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from prioridad_galicia.config import (  # noqa: E402
    COMPONENTES,
    ETIQUETAS,
    JUSTIFICACION_CORTA,
    NOMBRES_PRESET,
    PRESETS,
    SALIDA_GEOJSON,
    SALIDA_MANIFIESTO,
    SALIDA_VALIDACION,
)
from prioridad_galicia.index import calcular_prioridad, normalizar_pesos  # noqa: E402
from prioridad_galicia.normalize import robust_minmax  # noqa: E402
from prioridad_galicia.validation import evaluar, figura_quintiles  # noqa: E402

st.set_page_config(
    page_title="Prioridad territorial · Galicia",
    page_icon="🔥",
    layout="wide",
)


@st.cache_data
def cargar() -> pd.DataFrame:
    if not SALIDA_GEOJSON.exists():
        return pd.DataFrame()
    import geopandas as gpd

    datos = gpd.read_file(SALIDA_GEOJSON)
    datos["codigo_ine"] = datos["codigo_ine"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
    return datos


def main() -> None:
    st.title("Dónde actuar primero en Galicia")
    st.caption(
        "Índice municipal de prioridad para la prevención de incendios. "
        "El combustible sale de Sentinel-1 RTC (verano 2024). NISAR, si se procesa, no entra en la validación."
    )
    datos = cargar()
    if datos.empty:
        st.error(
            "No está `data/processed/municipios_indice.geojson`. "
            "Genera el índice con `python -m prioridad_galicia.cli pipeline`."
        )
        return

    with st.sidebar:
        st.header("Pesos")
        preset = st.selectbox(
            "Rol",
            list(PRESETS),
            format_func=lambda clave: NOMBRES_PRESET[clave],
        )
        st.caption(JUSTIFICACION_CORTA[preset])
        pesos = {}
        for componente in COMPONENTES:
            pesos[componente] = st.slider(
                ETIQUETAS[componente],
                min_value=0.0,
                max_value=1.0,
                value=float(PRESETS[preset][componente]),
                step=0.05,
                key=f"peso-{preset}-{componente}",
            )
        efectivos = normalizar_pesos(pesos)
        st.markdown("**Pesos efectivos** (suman 1)")
        for componente, valor in efectivos.items():
            st.write(f"{ETIQUETAS[componente]}: {valor:.0%}")
        usar_nisar = False
        if "vh_db_nisar" in datos.columns and datos["vh_db_nisar"].notna().any():
            usar_nisar = st.toggle(
                "Sustituir el combustible por NISAR L-band (2026)",
                value=False,
                help="No es comparable con la validación 2025-2026: NISAR es posterior.",
            )
        else:
            st.info("NISAR no está agregado. El combustible es Sentinel-1. El comando para procesarlo está en el README.")

    trabajo = datos.copy()
    if usar_nisar:
        trabajo["comb"] = robust_minmax(trabajo["vh_db_nisar"])
        st.warning("El mapa usa NISAR como combustible. La validación de abajo deja de ser retrospectiva.")
    trabajo = calcular_prioridad(trabajo, efectivos)
    trabajo["factor_etiqueta"] = trabajo["factor_dominante"].map(lambda valor: ETIQUETAS.get(valor, "—"))

    columna_mapa, columna_lista = st.columns([1.35, 0.85], gap="large")
    with columna_mapa:
        pulsado = _mapa(trabajo)
        codigo_pulsado = _codigo_desde_click(pulsado)
    with columna_lista:
        ranking = trabajo.sort_values("prioridad", ascending=False).head(10)
        st.subheader("Top 10")
        st.dataframe(
            ranking.assign(puesto=range(1, len(ranking) + 1))[
                ["puesto", "nombre", "provincia", "prioridad", "factor_etiqueta"]
            ].rename(columns={"factor_etiqueta": "factor dominante", "nombre": "municipio"}),
            hide_index=True,
            width="stretch",
        )
        opciones = trabajo.sort_values("nombre")
        etiquetas = {
            fila.codigo_ine: f"{fila.nombre} ({fila.provincia})" for fila in opciones.itertuples()
        }
        preseleccion = codigo_pulsado if codigo_pulsado in etiquetas else ranking.iloc[0]["codigo_ine"]
        elegido = st.selectbox(
            "Ficha del municipio",
            list(etiquetas),
            format_func=lambda codigo: etiquetas[codigo],
            index=list(etiquetas).index(preseleccion) if preseleccion in etiquetas else 0,
        )
        _ficha(trabajo.loc[trabajo["codigo_ine"] == elegido].iloc[0], efectivos)

    st.subheader("Validación retrospectiva 2025–2026")
    st.caption("Hectáreas EFFIS de 2025 y 2026 frente al ranking que producen los pesos de esta pantalla.")
    if trabajo["ha_quemadas_val"].notna().any():
        resumen = evaluar(trabajo)
        izquierda, derecha = st.columns([1, 1])
        with izquierda:
            captura = resumen["captura"].get("top_10", {})
            fraccion = captura.get("fraccion_ha")
            st.metric(
                "Hectáreas 2025–2026 dentro del 10 % de municipios con más prioridad",
                "—" if fraccion is None else f"{fraccion:.0%}",
                delta=None if fraccion is None else f"{fraccion - 0.10:+.0%} respecto al azar",
            )
            st.write(
                f"Municipios con algún perímetro EFFIS: {resumen['municipios_con_fuego']} de {resumen['n_municipios']}. "
                f"AUC de 'ardió algo': {resumen['auc'] if resumen['auc'] is not None else '—'}. "
                f"Hectáreas totales en el cruce: {resumen['ha_quemadas_validacion']:.0f}."
            )
        with derecha:
            st.pyplot(figura_quintiles(resumen), clear_figure=True)
    elif SALIDA_VALIDACION.exists():
        st.json(json.loads(SALIDA_VALIDACION.read_text(encoding="utf-8")))
    if SALIDA_MANIFIESTO.exists():
        with st.expander("De dónde sale cada capa"):
            manifiesto = json.loads(SALIDA_MANIFIESTO.read_text(encoding="utf-8"))
            st.json({clave: valor for clave, valor in manifiesto.items() if clave != "fases"})
            st.json(manifiesto.get("fases", {}))


def _mapa(datos: pd.DataFrame):
    gama = linear.YlOrRd_09.scale(0, 100)
    gama.caption = "Prioridad 0–100"
    centro = [42.75, -7.95]
    # CartoDB Positron en xyzservices exige apikey y, sin ella, pinta
    # «API KEY REQUIRED». Esta tesela de Esri es pública y no lleva clave.
    mapa = folium.Map(location=centro, zoom_start=8, tiles=None, control_scale=True)
    folium.TileLayer(
        tiles=(
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        ),
        attr="Esri, HERE, Garmin, © OpenStreetMap contributors",
        name="Base clara",
        max_zoom=16,
    ).add_to(mapa)
    geojson = json.loads(datos.to_json())

    def estilo(feature):
        valor = feature["properties"].get("prioridad")
        return {
            "fillColor": "#d6d3d1" if valor is None else gama(valor),
            "color": "#44403c",
            "weight": 0.4,
            "fillOpacity": 0.78,
        }

    folium.GeoJson(
        geojson,
        name="Prioridad",
        style_function=estilo,
        tooltip=folium.GeoJsonTooltip(
            fields=["nombre", "provincia", "prioridad", "factor_etiqueta"],
            aliases=["Municipio", "Provincia", "Prioridad", "Factor dominante"],
            localize=True,
        ),
    ).add_to(mapa)
    gama.add_to(mapa)
    return st_folium(
        mapa,
        height=640,
        use_container_width=True,
        returned_objects=["last_object_clicked"],
        key=f"mapa-{datos['prioridad'].round(1).sum():.0f}",
    )


def _codigo_desde_click(evento) -> str | None:
    if not evento:
        return None
    pulsado = evento.get("last_object_clicked") or {}
    props = pulsado.get("properties") or pulsado
    codigo = props.get("codigo_ine")
    if codigo is None:
        return None
    return str(codigo).replace(".0", "").zfill(5)


def _ficha(fila: pd.Series, pesos: dict[str, float]) -> None:
    st.markdown(f"### {fila['nombre']}")
    st.caption(f"{fila['provincia']} · INE {fila['codigo_ine']} · {fila.get('area_ha', float('nan')):.0f} ha")
    c1, c2, c3 = st.columns(3)
    c1.metric("Prioridad", f"{fila['prioridad']:.1f}" if pd.notna(fila["prioridad"]) else "—")
    c2.metric("Factor dominante", ETIQUETAS.get(fila["factor_dominante"], "—"))
    c3.metric("Quemado 2025–26", f"{fila.get('ha_quemadas_val', 0) or 0:.0f} ha")
    aportes = []
    for componente in COMPONENTES:
        valor = fila.get(componente)
        if pd.isna(valor):
            continue
        aportes.append(
            {
                "componente": ETIQUETAS[componente],
                "aporte": round(float(valor) * pesos[componente] * 100, 2),
            }
        )
    if aportes:
        st.bar_chart(pd.DataFrame(aportes).set_index("componente"), y="aporte")
        st.caption("Aporte al índice (peso × componente, en puntos sobre 100) antes de renormalizar huecos.")
    detalle = {
        "VH Sentinel-1 (dB)": _fmt(fila.get("vh_db")),
        "VH − VV (dB)": _fmt(fila.get("ratio_vh_vv_db")),
        "Observaciones SAR": _fmt(fila.get("n_obs_sar"), 0),
        "Bosque y matorral (WorldCover)": _fmt(fila.get("frac_forestal"), 2),
        "Incendios 2010–2024": _fmt(fila.get("n_incendios_hist"), 0),
        "ha quemadas / 1000 ha (2010–2024)": _fmt(fila.get("ha_quemadas_1000ha_hist")),
        "FWI medio verano 2024": _fmt(fila.get("fwi_medio")),
        "Población": _fmt(fila.get("poblacion"), 0),
        "hab/km²": _fmt(fila.get("densidad_hab_km2")),
        "km al parque de bomberos": _fmt(fila.get("dist_parque_km")),
        "km de vía principal / km²": _fmt(fila.get("densidad_viaria")),
        "VH NISAR (dB)": _fmt(fila.get("vh_db_nisar")),
    }
    st.dataframe(
        pd.DataFrame({"dato": list(detalle), "valor": list(detalle.values())}),
        hide_index=True,
        width="stretch",
    )


def _fmt(valor, decimales: int = 2) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or pd.isna(valor):
        return "—"
    if decimales == 0:
        return f"{float(valor):.0f}"
    return f"{float(valor):.{decimales}f}"


if __name__ == "__main__":
    main()
else:
    main()
