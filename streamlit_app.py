import streamlit as st
import pandas as pd
from google.cloud import firestore
from google.oauth2 import service_account

import json

import streamlit as st
import pandas as pd
import pydeck as pdk
from google.cloud import firestore

st.set_page_config(page_title="Citibikes NYC", layout="wide")
st.title("Citibikes NYC – Análisis de demanda por hora (Septiembre 2021)")


# ----------------------------------------------------------
# 1. Conexión a la base de Firestore
# ----------------------------------------------------------
@st.cache_resource
def get_firestore_client():
    key_dict = json.loads(st.secrets["textkey"])
    creds = service_account.Credentials.from_service_account_info(key_dict)
    return firestore.Client(credentials=creds, project="citibike")


# ----------------------------------------------------------
# 2. Cargar colección citibikes
# ----------------------------------------------------------
@st.cache_data
def load_citibike_data():
    db = get_firestore_client()
    docs = list(db.collection('citibikes').stream())
    docs_dict = [doc.to_dict() for doc in docs]

    df = pd.DataFrame(docs_dict)

    # Convertir a datetime
    df["started_at"] = pd.to_datetime(df["started_at"])
    df["ended_at"]   = pd.to_datetime(df["ended_at"])

    # Filtrar coordenadas válidas
    df = df.dropna(subset=["start_lat", "start_lng"])

    # Filtrar solo septiembre 2021
    df = df[
        (df["started_at"] >= "2021-09-01") &
        (df["started_at"] <  "2021-10-01")
    ]

    # Extraer columnas de fecha/hora
    df["date"] = df["started_at"].dt.date
    df["hour"] = df["started_at"].dt.hour

    return df


# ----------------------------------------------------------
# 3. Cargar datos
# ----------------------------------------------------------
data_load_state = st.text("Cargando datos desde Firestore...")
df = load_citibike_data()
data_load_state.text("Datos cargados")


# ----------------------------------------------------------
# 4. Selección de un día específico
# ----------------------------------------------------------
st.sidebar.header("Filtros")

unique_days = sorted(df["date"].unique())
selected_day = st.sidebar.selectbox("Selecciona un día de septiembre 2021", unique_days)

df_day = df[df["date"] == selected_day]

st.write(f"## Día seleccionado: {selected_day}")


# ----------------------------------------------------------
# 5. Histograma por hora (TODAS LAS ESTACIONES)
# ----------------------------------------------------------
st.write("###Histograma de viajes por hora del día")
hist = df_day["hour"].value_counts().sort_index()

st.bar_chart(hist)


# ----------------------------------------------------------
# 6. Seleccionar hora para análisis detallado
# ----------------------------------------------------------
selected_hour = st.sidebar.slider("Selecciona una hora del día", 0, 23, 8)
st.write(f"### Estaciones con mayor demanda a las {selected_hour}:00")


df_hour = df_day[df_day["hour"] == selected_hour]

# Agrupar por estación
demand = (
    df_hour.groupby(
        ["start_station_id", "start_station_name", "start_lat", "start_lng"]
    )
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=False)
)

st.dataframe(demand.head(20))


# ----------------------------------------------------------
# 7. Mapa de la ciudad con demanda por estación y hora
# ----------------------------------------------------------
st.write("###Mapa de estaciones donde se iniciaron recorridos en esta hora")

if not df_hour.empty:
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=demand,
        get_position=["start_lng", "start_lat"],
        get_radius="count * 5",
        get_color=[255, 0, 0],
        pickable=True
    )

    view_state = pdk.ViewState(
        latitude=demand["start_lat"].mean(),
        longitude=demand["start_lng"].mean(),
        zoom=12
    )

    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={"text": "Estación: {start_station_name}\nViajes: {count}"}
        )
    )
else:
    st.warning("No hay viajes en esta hora para este día.")
