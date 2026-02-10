import os
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI

# -----------------------------
# CONFIG STREAMLIT
# -----------------------------
st.set_page_config(page_title="Inventarios", layout="wide")
st.title("📦 Inventarios")

# -----------------------------
# GOOGLE SHEETS CONFIG
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

credenciales = Credentials.from_service_account_file(
    "service_account.json",
    scopes=SCOPES
)

client_gs = gspread.authorize(credenciales)
spreadsheet = client_gs.open_by_key(SHEET_ID)

# -----------------------------
# OPENAI CONFIG (ENV VAR)
# -----------------------------
client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# SIDEBAR
# -----------------------------
vista = st.sidebar.selectbox(
    "Selecciona vista",
    list(HOJAS.keys())
)

# -----------------------------
# CARGAR HOJA
# -----------------------------
worksheet = spreadsheet.worksheet(HOJAS[vista])
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# 🔒 BLINDAJE PARA PYARROW
df = df.astype(str)

# -----------------------------
# MOSTRAR DATA
# -----------------------------
st.subheader(f"📄 {vista}")
st.dataframe(df, width="stretch")

# -----------------------------
# IA SOBRE INVENTARIOS
# -----------------------------
st.divider()
st.subheader("🤖 Pregunta a la IA sobre esta hoja")

pregunta = st.text_input(
    "Ejemplo: ¿Cuántas entradas tuvo DAEWON en enero 2025?"
)

if st.button("Preguntar a la IA") and pregunta:
    with st.spinner("Analizando inventarios..."):
        prompt = f"""
Eres un analista experto en logística e inventarios.

Datos (tabla):
{df.head(50).to_string(index=False)}

Pregunta del usuario:
{pregunta}

Responde de forma clara, numérica y profesional.
"""

        respuesta = client_ai.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )

        st.success("Respuesta IA:")
        st.write(respuesta.output_text)


