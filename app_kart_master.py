
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
        }

        for target, aliases in mapping.items():
            for alias in aliases:
                if alias in df.columns:
                    df = df.rename(columns={alias: target})
                    break

        # 4. Nettoyage et Auto-détection des tours
        cols_to_convert = ['Vitesse', 'RPM', 'Eau', 'EGT', 'Distance', 'Lap']
        for col in cols_to_convert:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df.dropna(subset=['Vitesse', 'RPM'])

        # Création de la colonne Lap si absente (détection par reset de distance)
        if 'Lap' not in df.columns or df['Lap'].nunique() <= 1:
            if 'Distance' in df.columns:
                df['Lap'] = (df['Distance'].diff() < 0).cumsum() + 1
            else:
                df['Lap'] = 1

        # --- SECTION COMPARAISON ---
        laps = sorted(df['Lap'].dropna().unique().astype(int))
        
        if len(laps) > 1:
            st.header("⚔️ Comparaison de deux tours")
            c_sel1, c_sel2 = st.columns(2)
            with c_sel1:
                tour_a = st.selectbox("Tour de Référence (A)", laps, index=0)
            with c_sel2:
                tour_b = st.selectbox("Tour à Comparer (B)", laps, index=len(laps)-1)

            # Préparation des données comparatives
            df_a = df[df['Lap'] == tour_a].copy()
            df_b = df[df['Lap'] == tour_b].copy()

            # Normalisation de la distance pour superposition
            df_a['Dist_Norm'] = df_a['Distance'] - df_a['Distance'].min() if 'Distance' in df_a.columns else df_a.index
            df_b['Dist_Norm'] = df_b['Distance'] - df_b['Distance'].min() if 'Distance' in df_b.columns else df_b.index

            # Graphique de superposition
            fig_comp = go.Figure()
            fig_comp.add_trace(go.Scatter(x=df_a['Dist_Norm'], y=df_a['Vitesse'], 
                                          name=f"Tour {tour_a}", line=dict(color='#00CCFF', width=3)))
            fig_comp.add_trace(go.Scatter(x=df_b['Dist_Norm'], y=df_b['Vitesse'], 
                                          name=f"Tour {tour_b}", line=dict(color='#FF3300', width=3, dash='dash')))
            
            fig_comp.update_layout(
                title=f"Superposition Vitesse : Tour {tour_a} vs Tour {tour_b}",
                xaxis=dict(title="Distance sur le tour (m)"),
                yaxis=dict(title="Vitesse (km/h)"),
                template="plotly_dark",
                hovermode="x unified"
            )
            st.plotly_chart(fig_comp, use_container_width=True)
            
            

            # Metrics comparatives
            m1, m2, m3 = st.columns(3)
            diff_vmax = df_b['Vitesse'].max() - df_a['Vitesse'].max()
            m1.metric(f"Vmax Tour {tour_b}", f"{df_b['Vitesse'].max():.1f} km/h", f"{diff_vmax:.1f}")
            
            diff_rpm = df_b['RPM'].max() - df_a['RPM'].max()
            m2.metric(f"RPM Max Tour {tour_b}", f"{int(df_b['RPM'].max())}", f"{int(diff_rpm)}")
            
            if 'Eau' in df.columns:
                diff_eau = df_b['Eau'].max() - df_a['Eau'].max()
                m3.metric(f"Eau Max Tour {tour_b}", f"{df_b['Eau'].max():.1f} °C", f"{diff_eau:.1f}")

        # --- VERDICT IA ---
        st.divider()
        st.subheader("🤖 Verdict de l'Ingénieur")
        
        # On analyse le tour B (celui sélectionné pour comparaison)
        lap_target = tour_b if len(laps) > 1 else 1
        df_target = df[df['Lap'] == lap_target]
        
        conseils = []
        if category == "Rotax 125 Junior (J125)":
            max_r = df_target['RPM'].max()
            if max_r > 13800: conseils.append("⚙️ **Rapport :** Trop court. Tu satures. Enlève 1-2 dents.")
            elif max_r < 13200: conseils.append("⚙️ **Rapport :** Trop long. Ajoute des dents pour atteindre la puissance.")

        if 'Eau' in df.columns and df['Eau'].max() > 60:
            conseils.append("🔥 **Chauffe :** Moteur au dessus de 60°C. Vérifie le radiateur.")

        if not conseils: st.success("✅ Données optimales sur ce tour !")
        else:
            for c in conseils: st.write(f"- {c}")

    except Exception as e:
        st.error(f"❌ Erreur lors de l'analyse : {e}")
else:
    st.info("👋 Chargez un fichier CSV pour commencer la comparaison.")
