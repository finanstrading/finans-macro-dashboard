import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Finans Trading Dashboard",
    layout="wide"
)

SHEET_ID = "1dJB_3wWsSOkXm59dEJKYZlkK_wMlp89Pu1GObCNnyQU"
SHEET_NAME = "Dashboard_GBP"

csv_url = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?"
    f"tqx=out:csv&sheet={SHEET_NAME}"
)

st.title("📈 Finans Trading Dashboard")

try:
    df = pd.read_csv(csv_url)

    st.success("Conexión con Google Sheets realizada correctamente.")

    st.dataframe(df)

except Exception as e:
    st.error("No se pudo conectar con Google Sheets.")
    st.write(e)
