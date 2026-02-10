# CAMBIO FORZADO PARA GIT

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import re

# -----------------------------
# CONFIG STREAMLIT
# -----------------------------
st.set_page_config(page_title="Inventarios", layout="wide")
st.title("📦 Inventarios")

# -----------------------------
# CONSTANTES
# -----------------------------
SHEET_ID = "10vYjAS-dwG-dO0PsYMzUfoi_EIJzJXlbqrKcpYipYsY"

HOJAS = {
    "Entradas y Salidas": "Entradas y Salidas",
    "Inventario": "Inventario",
    "MODELO": "MODELO",
    "POR CLIENTE": "POR CLIENTE",
    "PackingList": "PackingList",
}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# -----------------------------
# FUNCIONES
# -----------------------------
def conectar_google_sheets():
    gcp = st.secrets["gcp_service_account"]
    private_key = gcp["private_key"].replace("\\n", "\n")

    service_account_info = {
        "type": gcp["type"],
        "project_id": gcp["project_id"],
        "private_key_id": gcp["private_key_id"],
        "private_key": private_key,
        "client_email": gcp["client_email"],
        "client_id": gcp["client_id"],
        "auth_uri": gcp["auth_uri"],
        "token_uri": gcp["token_uri"],
        "auth_provider_x509_cert_url": gcp["auth_provider_x509_cert_url"],
        "client_x509_cert_url": gcp["client_x509_cert_url"],
    }

    creds = Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)


def cargar_dataframe(spreadsheet, hoja):
    ws = spreadsheet.worksheet(hoja)
    df = pd.DataFrame(ws.get_all_records())
    return df.astype(str)


def detectar_cliente_y_anio(pregunta, df):
    p = pregunta.upper()
    cliente = None
    anio = None

    clientes_df = (
        df["Cliente"]
        .str.upper()
        .str.strip()
        .unique()
        .tolist()
        if "Cliente" in df.columns
        else []
    )

    for c in clientes_df:
        if c in p:
            cliente = c
            break

    match_anio = re.search(r"\b20\d{2}\b", p)
    if match_anio:
        anio = match_anio.group(0)

    return cliente, anio


def filtrar_dataframe(df, cliente, anio):
    df_f = df.copy()

    if cliente:
        df_f = df_f[
            df_f["Cliente"].str.upper().str.strip() == cliente
        ]

    if anio and "Fecha" in df_f.columns:
        df_f = df_f[df_f["Fecha"].str.contains(anio)]

    if "Cliente" in df_f.columns and df_f["Cliente"].nunique() > 1:
        st.error(f"Datos mezclados: {df_f['Cliente'].unique()}")
        st.stop()

    return df_f


def preguntar_a_ia(df_filtrado, pregunta, client_ai):
    prompt = f"""
Eres un analista experto en logística e inventarios.

Datos (UN SOLO CLIENTE):
{df_filtrado.to_string(index=False)}

Pregunta:
{pregunta}

Reglas:
- No inventes clientes.
- No asumas relaciones.
- Si no hay información suficiente, dilo.
"""

    r = client_ai.responses.create(
        model="gpt-4o-mini",
        input=prompt
    )
    return r.output_text


# -----------------------------
# EJECUCIÓN
# -----------------------------
spreadsheet = conectar_google_sheets()
client_ai = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# 👉 Vista SOLO para mostrar datos
vista = st.sidebar.selectbox("Selecciona vista", list(HOJAS.keys()))
df_vista = cargar_dataframe(spreadsheet, HOJAS[vista])

st.subheader(f"📄 {vista}")
st.dataframe(df_vista, use_container_width=True)

# -----------------------------
# CONSULTA IA (SIEMPRE INVENTARIO)
# -----------------------------
st.divider()
st.subheader("🤖 Pregunta a la IA")

pregunta = st.text_input("Ejemplo: Inventario SJM Enero 2026")

if st.button("Preguntar a la IA") and pregunta:

    # ⚠️ FUENTE REAL: Inventario
    df_inventario = cargar_dataframe(spreadsheet, "Inventario")

    cliente, anio = detectar_cliente_y_anio(pregunta, df_inventario)

    if cliente is None:
        st.warning("El cliente no existe en la hoja Inventario.")
        st.stop()

    df_filtrado = filtrar_dataframe(df_inventario, cliente, anio)

    if df_filtrado.empty:
        st.warning(f"No hay registros para {cliente} {anio or ''}")
        st.stop()

    with st.spinner("Analizando inventarios..."):
        respuesta = preguntar_a_ia(df_filtrado, pregunta, client_ai)
        st.success("Respuesta IA:")
        st.write(respuesta)





