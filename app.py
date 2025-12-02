import streamlit as st
import pandas as pd
import requests


# Carga de conjunto de datos

@st.cache_data
def cargar_datos():
    """
    Carga el archivo CSV descargado desde datos.gob.cl
    y deja solo los establecimientos de la Región Metropolitana.
    """
    df = pd.read_csv(
        "establecimientos_20251014.csv",
        sep=";",
        encoding="utf-8",
        encoding_errors="ignore"
    )

    # Filtrar solo para la región metropolitana
    df_rm = df[df["RegionGlosa"].str.contains("Metropolitana", na=False)].copy()

    # Asegurar que latitud y longitud sean numéricas
    df_rm["Latitud"] = pd.to_numeric(df_rm["Latitud"], errors="coerce")
    df_rm["Longitud"] = pd.to_numeric(df_rm["Longitud"], errors="coerce")

    # construir dirección a partir de las columnas del CSV
    df_rm["Direccion"] = (
        df_rm["TipoViaGlosa"].fillna("") + " " +
        df_rm["NombreVia"].fillna("") + " " +
        df_rm["Numero"].fillna("").astype(str)
    ).str.strip()

    # Clasificación entre: Público / Privado / Otro
    def clasificar(dep):
        if not isinstance(dep, str):
            return "Otro"
        d = dep.lower()
        if "privad" in d:
            return "Privado"
        if "municipal" in d or "servicio de salud" in d or "seremi" in d:
            return "Público"
        return "Otro"

    df_rm["SistemaSalud"] = df_rm["DependenciaAdministrativa"].apply(clasificar)

    return df_rm



# API datos.gob.cl

@st.cache_data
def consultar_api_datos_gob(resource_id: str, limit: int = 50):
    """
    Ejemplo de uso de la API REST de datos.gob.cl usando datastore_search.
    """
    url = "https://datos.gob.cl/api/3/action/datastore_search"
    params = {"resource_id": resource_id, "limit": limit}

    try:
        r = requests.get(url, params=params, timeout=10)
    except requests.exceptions.RequestException as e:
        st.error(f"Error de conexión con datos.gob.cl: {e}")
        return None

    if r.status_code != 200:
        st.error(f"Error al obtener datos (status code {r.status_code}).")
        return None

    data = r.json()
    if not data.get("success", False):
        st.warning("La API respondió pero 'success' es False. Revisa el resource_id.")
        return None

    records = data.get("result", {}).get("records", [])
    if not records:
        st.info("La API no devolvió registros para este recurso.")
        return None

    return pd.DataFrame(records)



# Como se vera la pagina

st.set_page_config(
    page_title="Centros de Salud RM",
    layout="wide"
)

st.title("Centros de Salud — Región Metropolitana")
st.write(
    "Aplicación para explorar establecimientos de salud de la Región Metropolitana "
    "utilizando datos abiertos de datos.gob.cl."
)

st.html(
    """
    <div style='background-color:#f5f5f5; padding: 16px 20px; border-radius: 8px;
                border-left: 5px solid #ff4b4b; font-size: 20px; line-height: 1.6;'>
        <b>¿Cómo usar esta página? (paso a paso)</b><br><br>
        1. En el menú de la izquierda, elige primero la <b>comuna</b> donde quieres buscar un centro de salud.<br>
        2. Luego puedes seleccionar el <b>tipo de establecimiento</b> (consultorio, hospital, CESFAM, SAPU, etc.).<br>
        3. También puedes elegir si quieres ver solo centros <b>públicos</b>, <b>privados</b> u <b>otros</b>, 
           y el <b>nivel de atención</b> (primario, secundario, etc.).<br>
        4. El <b>mapa</b> mostrará los centros que cumplen con esos filtros y el gráfico mostrará las comunas con más centros.<br>
        5. Más abajo verás la <b>tabla de establecimientos</b> con nombre, comuna, dirección y teléfono. 
           Puedes moverla hacia la derecha y hacia abajo para ver toda la información.<br>
        6. Si quieres volver a ver todos los centros, borra el texto de búsqueda y selecciona nuevamente 
           <b>todas las opciones</b> en los filtros de la izquierda.
    </div>
    """
)


df = cargar_datos()


# Filtros aplicados en la barra lateral

st.sidebar.header("Filtros")

# opciones
comunas = sorted(df["ComunaGlosa"].dropna().unique())
tipos = sorted(df["TipoEstablecimientoGlosa"].dropna().unique())
sistemas = sorted(df["SistemaSalud"].dropna().unique())
niveles = sorted(df["NivelAtencionEstabglosa"].dropna().unique())

nombre_filtro = st.sidebar.text_input("Buscar por nombre")

comunas_sel = st.sidebar.multiselect("Comuna", comunas, default=comunas)
tipos_sel = st.sidebar.multiselect("Tipo de establecimiento", tipos, default=tipos)
sistemas_sel = st.sidebar.multiselect("Sistema (Público/Privado/Otro)", sistemas, default=sistemas)
niveles_sel = st.sidebar.multiselect("Nivel de atención", niveles, default=niveles)

# orden simple A-Z / Z-A por nombre
orden_campo = st.sidebar.selectbox("Ordenar por", ["Nombre", "Comuna"])
orden_dir = st.sidebar.radio("Dirección", ["A → Z", "Z → A"], horizontal=True)

columna_orden = "EstablecimientoGlosa" if orden_campo == "Nombre" else "ComunaGlosa"
asc = True if orden_dir.startswith("A") else False

# aplicar filtros
df_filtrado = df.copy()

if nombre_filtro:
    df_filtrado = df_filtrado[
        df_filtrado["EstablecimientoGlosa"].str.contains(nombre_filtro, case=False, na=False)
    ]

df_filtrado = df_filtrado[
    df_filtrado["ComunaGlosa"].isin(comunas_sel)
    & df_filtrado["TipoEstablecimientoGlosa"].isin(tipos_sel)
    & df_filtrado["SistemaSalud"].isin(sistemas_sel)
    & df_filtrado["NivelAtencionEstabglosa"].isin(niveles_sel)
]

df_filtrado = df_filtrado.sort_values(by=columna_orden, ascending=asc)


# Resumen (como métricas simples)

st.subheader("Resumen (datos filtrados)")

c1, c2, c3 = st.columns(3)
c1.metric("Total establecimientos", len(df_filtrado))
c2.metric("Públicos", int((df_filtrado["SistemaSalud"] == "Público").sum()))
c3.metric("Privados", int((df_filtrado["SistemaSalud"] == "Privado").sum()))


# Mapa y gráfico

col_mapa, col_graf = st.columns([2, 1])

with col_mapa:
    st.markdown("### Mapa de centros de salud")
    df_mapa = df_filtrado.dropna(subset=["Latitud", "Longitud"]).copy()
    if df_mapa.empty:
        st.info("No hay establecimientos con coordenadas para los filtros seleccionados.")
    else:
        df_mapa = df_mapa.rename(columns={"Latitud": "lat", "Longitud": "lon"})
        st.map(df_mapa[["lat", "lon"]], zoom=10)

st.subheader("Top 5 comunas con más centros de salud")
top_comunas = df_filtrado["ComunaGlosa"].value_counts().head(5)
st.bar_chart(top_comunas)


# Tabla debajo

st.markdown("### Tabla de establecimientos (detalle)")

columnas_tabla = [
    "EstablecimientoGlosa",       
    "TipoEstablecimientoGlosa",   
    "ComunaGlosa",                
    "Direccion",                  
    "SistemaSalud",               
    "NivelAtencionEstabglosa",    
    "TelefonoMovil_TelefonoFijo"  
]

cols_existentes = [c for c in columnas_tabla if c in df_filtrado.columns]
st.dataframe(df_filtrado[cols_existentes], use_container_width=True)


# La opción del Feedback

st.markdown("---")
st.markdown("### Opinión / Feedback")

texto_feedback = st.text_area("Escribe aquí tus comentarios sobre la aplicación")

if st.button("Enviar feedback"):
    if texto_feedback.strip():
        st.success("¡Gracias por tu feedback! (solo se muestra en pantalla, no se guarda).")
    else:
        st.warning("Por favor, escribe algo antes de enviar.")


# Sección de API datos.gob.cl

st.write("---")
st.subheader("Consultar datos desde API datos.gob.cl")

resource_id_input = st.text_input(
    "Resource ID de datos.gob.cl",
    value="2c44d782-3365-44e3-aefb-2c8b8363a1bc",
)

limite_api = st.number_input(
    "Cantidad de filas a descargar",
    min_value=10,
    max_value=200,
    value=30,
)

if st.button("Consultar API datos.gob.cl"):
    df_api = consultar_api_datos_gob(resource_id_input.strip(), int(limite_api))

    if df_api is not None and not df_api.empty:
        st.success("Datos obtenidos correctamente desde la API.")
        st.write(f"Filas totales recibidas: **{len(df_api)}**")
        st.dataframe(df_api, use_container_width=True, height=400)
    else:
        st.warning("La API no devolvió registros para mostrar.")
