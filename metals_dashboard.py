import streamlit as st
from gold_dashboard import render_gold_dashboard, compact_selector

def render_metals_dashboard():
    st.markdown('''<div class="dashboard-header"><div class="dashboard-eyebrow">MACRO FX · METALES</div><div class="dashboard-title">Metales</div><div class="dashboard-subtitle">Análisis fundamental de oro, plata y cobre</div></div>''',unsafe_allow_html=True)
    metal=compact_selector('Metal',['ORO','PLATA','COBRE'],'metals_selector','ORO')
    if metal=='ORO': render_gold_dashboard()
    else: st.info(f'{metal}: sección reservada para una próxima fase.')
