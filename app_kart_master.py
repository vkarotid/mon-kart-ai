import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sqlite3
from datetime import datetime
from io import StringIO

# --- CONFIGURATION ---
st.set_page_config(page_title="Karting AI Pro - Comparaison", layout="wide", page_icon="🏁")

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
    category = st.selectbox("Type de Moteur", ["Mini 60", "Rotax 125 Junior (J125)", "Rotax Max (Senior)"], key="motor_select")
    st.divider()
    st.subheader("🌤️ Météo")
    t_air = st.slider("Température Air (°C)", -5, 45, 20)
    g_actuel = st.number_input("Gicleur actuel", value=122)
    if "Rotax" in category:
        st.warning(f"🔧 Gicleur suggéré : **{int(g_actuel + (20 - t_air) / 5)}**")

# --- MAIN ---
st.title("🏎️ Karting AI Telemetry Analyzer")

file_user = st.file_uploader("📂 Téléverser le fichier CSV (Session Complète)", type=["csv"])

if file_user:
    try:
        raw_content = file_user.read().decode('utf-8').splitlines()
        header_index = 0
        for i, line in enumerate(raw_content):
            if any(k in line for k in ["Distance", "Speed", "RPM", "GPS", "Lap"]):
                header_index = i
                break
        
        data_str = "\n".join(raw_content[header_index:])
        df = pd.read_csv(StringIO(data_str), sep=None, engine='python', on_bad_lines='skip')
        df.columns = [c.strip().replace('"', '') for c in df.columns]

        # Mappeur
        mapping = {
            'Vitesse': ['GPS_Speed', 'Speed', 'GPS Speed', 'VehicleSpeed', 'Vitesse'],
            'RPM': ['RPM', 'EngineSpeed', 'Eng_RPM', 'Moteur_RPM', 'RPM_Moteur'],
            'Eau': ['Water_Temp', 'WaterTemp', 'ECT', 'Temp_Eau', 'Temp_H2O', 'Water'],
            'Distance': ['Distance', 'Dist', 'GPS_Distance'],
            'Lap': ['Lap', 'LapNumber', 'Tour', 'Lap_Number', 'Lap_No']
        }

        for target, aliases in mapping.items():
            for alias in aliases:
                if alias in df.columns:
                    df = df.rename(columns={alias: target})
                    break

        # Nettoyage
        cols_to_convert = ['Vitesse', 'RPM', 'Eau', 'Distance', 'Lap']
        for col in cols_to_convert:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['Vitesse', 'RPM'])

        # --- ANALYSE ET COMPARAISON ---
        if 'Lap' in df.columns:
            laps = sorted(df['Lap'].dropna().unique().astype(int))
            
            st.header("⚔️ Comparaison de Tours")
            col_sel1, col_sel2 = st.columns(2)
            with col_sel1:
                tour_a = st.selectbox("Sélectionner le Tour A (Référence)", laps, index=0)
            with col_sel2:
                tour_b = st.selectbox("Sélectionner le Tour B (À comparer)", laps, index=len(laps)-1 if len(laps)>1 else 0)

            # Préparation des données de comparaison
            df_a = df[df['Lap'] == tour_a].reset_index()
            df_b = df[df['Lap'] == tour_b].reset_index()

            # Graphique de comparaison
            fig_comp = go.Figure()
            
            # Tour A
            fig_comp.add_trace(go.Scatter(x=df_a['Distance'], y=df_a['Vitesse'], 
                                          name=f"Tour {tour_a} (Vitesse)", line=dict(color='#00CCFF', width=3)))
            # Tour B
            fig_comp.add_trace(go.Scatter(x=df_b['Distance'], y=df_b['Vitesse'], 
                                          name=f"Tour {tour_b} (Vitesse)", line=dict(color='#FF3300', width=3, dash='dash')))
            
            fig_comp.update_layout(
                title=f"Superposition : Tour {tour_a} vs Tour {tour_b}",
                xaxis=dict(title="Distance (m)"),
                yaxis=dict(title="Vitesse (km/h)"),
                hovermode="x unified",
                template="plotly_dark",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_comp, use_container_width=True)

            # Comparaison des stats
            c1, c2, c3 = st.columns(3)
            diff_vmax = df_b['Vitesse'].max() - df_a['Vitesse'].max()
            c1.metric(f"Vmax Tour {tour_b}", f"{df_b['Vitesse'].max():.1f} km/h", f"{diff_vmax:.1f} km/h")
            
            diff_rpm = df_b['RPM'].max() - df_a['RPM'].max()
            c2.metric(f"RPM Max Tour {tour_b}", f"{int(df_b['RPM'].max())}", f"{int(diff_rpm)}")
            
            if 'Eau' in df.columns:
                diff_eau = df_b['Eau'].max() - df_a['Eau'].max()
                c3.metric(f"Temp Eau Tour {tour_b}", f"{df_b['Eau'].max():.1f} °C", f"{diff_eau:.1f} °C")

        else:
            st.warning("⚠️ La colonne 'Lap' est absente. Impossible de comparer les tours.")

        # --- VERDICT ---
        st.divider()
        st.subheader("🤖 Verdict de l'Ingénieur")
        if category == "Rotax 125 Junior (J125)":
            if df['RPM'].max() > 13800:
                st.write("- **Transmission :** Le régime max est très élevé sur cette session. Envisage de rallonger.")
        if 'Eau' in df.columns and df['Eau'].max() > 60:
            st.error("- **Chauffe :** Température excessive détectée en fin de session.")

    except Exception as e:
        st.error(f"❌ Erreur : {e}")
else:
    st.info("👋 Chargez un fichier CSV AiM pour comparer vos tours.")
