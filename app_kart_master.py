import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sqlite3
from datetime import datetime
from io import StringIO

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Karting AI Pro - Expert", layout="wide", page_icon="🏁")

# --- INITIALISATION BASE DE DONNÉES ---
def init_db():
    conn = sqlite3.connect('karting_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT, circuit TEXT, categorie TEXT, chrono TEXT,
                  gicleur INTEGER, couronne INTEGER, vmax REAL, rpm_max REAL, verdict TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- BARRE LATÉRALE ---
with st.sidebar:
    st.title("🏁 Configuration")
    category = st.selectbox("Type de Moteur", ["Mini 60", "Rotax 125 Junior (J125)", "Rotax Max (Senior)"], key="motor_sel")
    
    st.divider()
    st.subheader("🌤️ Météo & Carburation")
    t_air = st.slider("Température Air (°C)", -5, 45, 20)
    g_actuel = st.number_input("Gicleur actuel", value=122)
    
    if "Rotax" in category:
        g_suggere = int(g_actuel + (20 - t_air) / 5)
        st.warning(f"🔧 Gicleur suggéré : **{g_suggere}**")
    
    st.divider()
    st.info("💡 **Aide Export :** Pour une analyse parfaite, exportez en CSV avec 'Distance' et 'Lap Number' depuis AiM.")

# --- INTERFACE PRINCIPALE ---
st.title("🏎️ Karting AI Telemetry Analyzer")

file_user = st.file_uploader("📂 Téléverser le fichier CSV (Session Complète)", type=["csv"])

if file_user:
    try:
        # 1. Lecture brute et détection intelligente du header
        raw_content = file_user.read().decode('utf-8').splitlines()
        header_index = 0
        for i, line in enumerate(raw_content):
            if any(k in line for k in ["Distance", "Speed", "RPM", "GPS", "Lap", "Time"]):
                header_index = i
                break
        
        # 2. Chargement Pandas
        data_str = "\n".join(raw_content[header_index:])
        df = pd.read_csv(StringIO(data_str), sep=None, engine='python', on_bad_lines='skip')
        
        # Nettoyage des colonnes
        df.columns = [c.strip().replace('"', '') for c in df.columns]

        # 3. Mappeur de colonnes (Standardisation)
        mapping = {
            'Vitesse': ['GPS_Speed', 'Speed', 'GPS Speed', 'VehicleSpeed', 'Vitesse'],
            'RPM': ['RPM', 'EngineSpeed', 'Eng_RPM', 'Moteur_RPM', 'RPM_Moteur'],
            'Eau': ['Water_Temp', 'WaterTemp', 'ECT', 'Temp_Eau', 'Temp_H2O', 'Water'],
            'EGT': ['EGT', 'Exhaust_Temp', 'Temp_Echap', 'EGT_1'],
            'Distance': ['Distance', 'Dist', 'GPS_Distance'],
            'Lap': ['Lap', 'LapNumber', 'Tour', 'Lap_Number', 'Lap_No']
