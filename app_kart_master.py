import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sqlite3
from datetime import datetime
from io import StringIO

# --- CONFIGURATION ---
st.set_page_config(page_title="Karting AI Pro", layout="wide", page_icon="🏁")

# --- INITIALISATION DB ---
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

# --- SIDEBAR ---
with st.sidebar:
    st.title("🏁 Configuration")
    category = st.selectbox("Type de Moteur", ["Mini 60", "Rotax 125 Junior (J125)", "Rotax Max (Senior)"], key="motor_sel")
    st.divider()
    t_air = st.slider("Température Air (°C)", -5, 45, 20)
    g_actuel = st.number_input("Gicleur actuel", value=122)
    if "Rotax" in category:
        st.warning(f"🔧 Gicleur suggéré : **{int(g_actuel + (20 - t_air) / 5)}**")

st.title("🏎️ Karting AI Telemetry Analyzer")
file_user = st.file_uploader("📂 Téléverser le fichier CSV AiM", type=["csv"])

if file_user:
    try:
        # 1. Lecture et détection du Header
        raw_content = file_user.read().decode('utf-8').splitlines()
        header_index = 0
        for i, line in enumerate(raw_content):
            # On cherche une ligne qui contient des mots clés courants
            if any(k in line for k in ["Distance", "Speed", "RPM", "GPS", "Time", "Vitesse"]):
                header_index = i
                break
        
        data_str = "\n".join(raw_content[header_index:])
        df = pd.read_csv(StringIO(data_str), sep=None, engine='python', on_bad_lines='skip')
        df.columns = [c.strip().replace('"', '') for c in df.columns]

        # 2. Mappeur de colonnes étendu
        mapping = {
            'Vitesse': ['GPS_Speed', 'Speed', 'GPS Speed', 'VehicleSpeed', 'Vitesse', 'V_GPS', 'GPS_Vitesse'],
            'RPM': ['RPM', 'EngineSpeed', 'Eng_RPM', 'Moteur_RPM', 'RPM_Moteur', 'Moteur', 'RPM_1'],
            'Eau': ['Water_Temp', 'WaterTemp', 'ECT', 'Temp_Eau', 'Temp_H2O', 'Water', 'T_Eau'],
            'Distance': ['Distance', 'Dist', 'GPS_Distance', 'Distance_GPS'],
            'Lap': ['Lap', 'LapNumber', 'Tour', 'Lap_Number', 'Lap_No', 'No_Tour']
        }

        found_cols = {}
        for target, aliases in mapping.items():
            for alias in aliases:
                if alias in df.columns:
                    df = df.rename(columns={alias: target})
                    found_cols[target] = True
                    break

        # --- DIAGNOSTIC SI ERREUR ---
        if 'Vitesse' not in df.columns or 'RPM' not in df.columns:
            st.error("❌ Impossible de trouver 'Vitesse' ou 'RPM' dans votre fichier.")
            st.write("Voici les noms de colonnes détectés dans votre export :")
            st.code(list(df.columns))
            st.info("💡 Allez dans RaceStudio > Export et assurez-vous de cocher 'GPS Speed' et 'RPM'.")
            st.stop()

        # 3. Nettoyage
        for col in ['Vitesse', 'RPM', 'Eau', 'Distance', 'Lap']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['Vitesse', 'RPM'])

        # 4. Auto-détection des tours
        if 'Lap' not in df.columns or df['Lap'].nunique() <= 1:
            if 'Distance' in df.columns:
                df['Lap'] = (df['Distance'].diff() < 0).cumsum() + 1
            else:
                df['Lap'] = 1

        # --- COMPARAISON ---
        laps = sorted(df['Lap'].dropna().unique().astype(int))
        if len(laps) > 1:
            st.header("⚔️ Comparaison de Tours")
            c1, c2 = st.columns(2)
            tour_a = c1.selectbox("Tour de Référence (A)", laps, index=min(1, len(laps)-1))
            tour_b = c2.selectbox("Tour à Comparer (B)", laps, index=len(laps)-1)

            df_a = df[df['Lap'] == tour_a].copy()
            df_b = df[df['Lap'] == tour_b].copy()
            df_a['D_Norm'] = df_a['Distance'] - df_a['Distance'].min() if 'Distance' in df_a.columns else df_a.index
            df_b['D_Norm'] = df_b['Distance'] - df_b['Distance'].min() if 'Distance' in df_b.columns else df_b.index

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_a['D_Norm'], y=df_a['Vitesse'], name=f"Tour {tour_a}", line=dict(color='#00CCFF', width=3)))
            fig.add_trace(go.Scatter(x=df_b['D_Norm'], y=df_b['Vitesse'], name=f"Tour {tour_b}", line=dict(color='#FF3300', width=3, dash='dash')))
            fig.update_layout(template="plotly_dark", hovermode="x unified", xaxis_title="Distance (m)", yaxis_title="Vitesse (km/h)")
            st.plotly_chart(fig, use_container_width=True)

            m1, m2 = st.columns(2)
            m1.metric(f"Vmax Tour {tour_b}", f"{df_b['Vitesse'].max():.1f} km/h", f"{df_b['Vitesse'].max() - df_a['Vitesse'].max():.1f}")
            m2.metric(f"RPM Max Tour {tour_b}", f"{int(df_b['RPM'].max())}", f"{int(df_b['RPM'].max() - df_a['RPM'].max())}")

    except Exception as e:
        st.error(f"❌ Erreur critique : {e}")
