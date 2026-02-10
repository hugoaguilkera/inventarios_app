import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import re

# =====================================================
# CONFIGURACIÓN STREAMLIT (UI)
# =====================================================
st.set_page_config(
    page_title="Inventarios",
    layout="wide"
)
st.title("📦 Inventarios")

# =====================================================
# CONSTANTES GLOBALES
# =====================================================
SHEET_ID = "10vYjAS-dwG-dO0PsYMzUfoi_EIJzJXlbqrKcpYipYsY"

HOJAS = {
    "Entradas y Salidas": "Entradas y Salidas",
    "Inventario": "Inventario",
    "Kardex": None,              # 👈 NO es hoja real
    "MODELO": "MODELO",
    "POR CLIENTE": "POR CLIENTE",
    "PackingList": "PackingList",
}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# =====================================================
# FUNCIONES DE CONEXIÓN Y CARGA
# =====================================================
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
        service_account_info,
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)


def cargar_dataframe(spreadsheet, hoja):
    ws = spreadsheet.worksheet(hoja)
    df = pd.DataFrame(ws.get_all_records())
    return df.astype(str)

# =====================================================
# FUNCIONES DE SOPORTE IA
# =====================================================
def detectar_cliente_y_anio(pregunta, df):
    p = pregunta.upper()
    cliente = None
    anio = None

    if "Cliente" in df.columns:
        for c in df["Cliente"].str.upper().str.strip().unique():
            if c in p:
                cliente = c
                break

    match = re.search(r"\b20\d{2}\b", p)
    if match:
        anio = match.group(0)

    return cliente, anio


def filtrar_dataframe(df, cliente, anio):
    df_f = df.copy()

    if cliente:
        df_f = df_f[df_f["Cliente"].str.upper().str.strip() == cliente]

    if anio and "Fecha" in df_f.columns:
        df_f = df_f[df_f["Fecha"].str.contains(anio)]

    return df_f


def preguntar_a_ia(df_filtrado, pregunta, client_ai):
    prompt = f"""
Eres un analista experto en logística e inventarios.

Datos (UN SOLO CLIENTE):
{df_filtrado.to_string(index=False)}

Pregunta:
{pregunta}

Reglas:
- No inventes clientes
- No asumas relaciones
- Si no hay información suficiente, dilo
"""

    r = client_ai.responses.create(
        model="gpt-4o-mini",
        input=prompt
    )
    return r.output_text

# =====================================================
# FUNCIÓN KARDEX
# =====================================================
def generar_kardex(df_movimientos, cliente, modelo=None):
    df = df_movimientos.copy()

    df["Cliente"] = df["Cliente"].str.upper().str.strip()
    df["Tipo de Movimiento"] = df["Tipo de Movimiento"].str.upper().str.strip()
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["Piezas"] = pd.to_numeric(df["Piezas"], errors="coerce").fillna(0)

    df = df[df["Cliente"] == cliente]

    if modelo:
        df = df[df["Modelo"] == modelo]

    df = df.sort_values("Fecha")

    df["Movimiento"] = df.apply(
        lambda r: r["Piezas"]
        if r["Tipo de Movimiento"] == "ENTRADA"
        else -r["Piezas"],
        axis=1
    )

    df["Saldo"] = df["Movimiento"].cumsum()

    return df[
        ["Fecha", "Tipo de Movimiento", "Modelo", "Piezas", "Movimiento", "Saldo"]
    ]
# -----------------------------
# FUNCIÓN REPORTE DIARIO OPERATIVO
# -----------------------------
def generar_reporte_diario_operativo(df_movimientos, fecha):
    df = df_movimientos.copy()

    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["Piezas"] = pd.to_numeric(df["Piezas"], errors="coerce").fillna(0)
    df["Tipo de Movimiento"] = df["Tipo de Movimiento"].str.upper().str.strip()
    df["Cliente"] = df["Cliente"].str.upper().str.strip()

    fecha = pd.to_datetime(fecha)
    df = df[df["Fecha"] == fecha]

    df["Entrada"] = df.apply(
        lambda r: r["Piezas"] if r["Tipo de Movimiento"] == "ENTRADA" else 0,
        axis=1
    )
    df["Salida"] = df.apply(
        lambda r: r["Piezas"] if r["Tipo de Movimiento"] == "SALIDA" else 0,
        axis=1
    )

    resumen = (
        df.groupby("Cliente", as_index=False)
        .agg({"Entrada": "sum", "Salida": "sum"})
    )

    resumen["Neto"] = resumen["Entrada"] - resumen["Salida"]

    return df, resumen


# -----------------------------
# EJECUCIÓN
# -----------------------------
spreadsheet = conectar_google_sheets()
client_ai = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

vista = st.sidebar.selectbox("Selecciona vista", list(HOJAS.keys()))

# -----------------------------
# VISTA KARDEX
# -----------------------------
if vista == "Kardex":
    st.subheader("📊 Kardex")

    df_mov = cargar_dataframe(spreadsheet, "Entradas y Salidas")

    cliente_sel = st.selectbox("Selecciona cliente", sorted(df_mov["Cliente"].unique()))
    modelo_sel = st.selectbox(
        "Selecciona modelo (opcional)",
        ["Todos"] + sorted(df_mov["Modelo"].unique())
    )

    modelo_filtro = None if modelo_sel == "Todos" else modelo_sel
    df_kardex = generar_kardex(df_mov, cliente_sel, modelo_filtro)

    st.dataframe(df_kardex, use_container_width=True)
    st.stop()


# -----------------------------
# VISTAS NORMALES
# -----------------------------
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

# -----------------------------
# FUNCIÓN KARDEX / CUADRE
# -----------------------------
def generar_reporte_cuadre_inventario_kardex(df_mov, df_inv):
    """
    Genera reporte de cuadre entre Kardex (Entradas y Salidas)
    y la hoja Inventario.
    """

    # --- KARDEX ---
    kardex = df_mov.copy()

    kardex["Cliente"] = kardex["Cliente"].str.upper().str.strip()
    kardex["Modelo"] = kardex["Modelo"].str.upper().str.strip()
    kardex["Lote"] = kardex["Lote"].str.upper().str.strip()
    kardex["Tipo"] = kardex["Tipo"].str.upper().str.strip()

    kardex["Movimiento"] = kardex.apply(
        lambda r: r["Piezas"] if r["Tipo"] == "ENTRADA" else -r["Piezas"],
        axis=1
    )

    kardex = (
        kardex
        .groupby(["Cliente", "Modelo", "Lote"], as_index=False)["Movimiento"]
        .sum()
        .rename(columns={"Movimiento": "Saldo_Kardex"})
    )

    # --- INVENTARIO ---
    inv = df_inv.copy()

    inv["Cliente"] = inv["Cliente"].str.upper().str.strip()
    inv["Modelo"] = inv["Modelo"].str.upper().str.strip()
    inv["Lote"] = inv["Lote"].str.upper().str.strip()

    inv = inv.rename(columns={"Piezas en stock": "Inventario"})
    inv = inv[["Cliente", "Modelo", "Lote", "Inventario"]]

    # --- CRUCE ---
    cuadre = kardex.merge(
        inv,
        on=["Cliente", "Modelo", "Lote"],
        how="left"
    )

    cuadre["Inventario"] = cuadre["Inventario"].fillna(0).astype(int)
    cuadre["Diferencia"] = cuadre["Inventario"] - cuadre["Saldo_Kardex"]

    cuadre["Estatus"] = cuadre["Diferencia"].apply(
        lambda x: "OK" if x == 0 else "REVISAR"
    )

    return cuadre
