import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from fpdf import FPDF
import sqlite3
from datetime import datetime
import io

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Karting AI Engineer", layout="wide", page_icon="🏁")

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

# --- FONCTIONS TECHNIQUES ---
def generate_pdf_report(stats, conseils, category):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 10, f"Rapport d'Analyse : {category}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, " Donnees de Performance", ln=True)
    pdf.set_font("Arial", size=12)
    for k, v in stats.items():
        pdf.cell(0, 8, f"{k} : {v}", ln=True)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, " Verdict de l'Ingenieur", ln=True)
    pdf.set_font("Arial", size=11)
    for c in conseils:
        clean_text = c.encode('latin-1', 'ignore').decode('latin-1')
        pdf.multi_cell(0, 8, f"- {clean_text}")
    return pdf.output()

def calculer_gicleur_rotax(temp_air, g_actuel):
    correction = (20 - temp_air) / 5
    return int(g_actuel + correction)

# --- BARRE LATÉRALE ---
with st.sidebar:
    st.title("🏁 Configuration")
    category = st.selectbox("Moteur", ["Mini 60", "Rotax 125 Junior (J125)", "Rotax Max (Senior)"])
    
    st.divider()
    st.subheader("🌤️ Météo & Carburation")
    t_air = st.slider("Température Air (°C)", -5, 45, 20)
    g_actuel = st.number_input("Gicleur actuel", value=122)
    
    if "Rotax" in category:
        g_suggere = calculer_gicleur_rotax(t_air, g_actuel)
        st.warning(f"🔧 Gicleur suggéré : **{g_suggere}**")

# --- INTERFACE PRINCIPALE ---
st.title("🏎️ Karting AI Telemetry Analyzer")

with st.expander("📖 GUIDE D'UTILISATION (Cliquez pour ouvrir)", expanded=False):
    st.markdown("""
    1. **Export :** Dans RaceStudio 3, exportez votre tour en **CSV**.
    2. **Colonnes :** Assurez-vous d'avoir *Distance, GPS_Speed, RPM, GPS_LatAcc, GPS_LonAcc, Water_Temp, EGT*.
    3. **Analyse :** Téléversez le fichier ci-dessous pour le verdict IA.
    """)

file_user = st.file_uploader("📂 Téléverser le fichier CSV de RaceStudio", type=["csv"])

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from fpdf import FPDF
import sqlite3
from datetime import datetime
from io import StringIO

# --- CONFIGURATION ---
st.set_page_config(page_title="Karting AI Pro", layout="wide", page_icon="🏁")

# --- DATABASE ---
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

# --- INTERFACE ---
with st.sidebar:
    st.title("🏁 Configuration")
    category = st.selectbox("Moteur", ["Mini 60", "Rotax 125 Junior (J125)", "Rotax Max (Senior)"])
    st.divider()
    st.subheader("🌤️ Météo")
    t_air = st.slider("Température Air (°C)", -5, 45, 20)
    g_actuel = st.number_input("Gicleur actuel", value=122)

st.title("🏎️ Karting AI Telemetry Analyzer")

file_user = st.file_uploader("📂 Téléverser le fichier CSV (Session Complète)", type=["csv"])

if file_user:
    try:
        # 1. Lecture brute et détection du header
        raw_data = file_user.read().decode('utf-8').splitlines()
        header_index = 0
        for i, line in enumerate(raw_data):
            if any(k in line for k in ["Distance", "Speed", "RPM", "GPS"]):
                header_index = i
                break
        
        # 2. Chargement Pandas
        df = pd.read_csv(StringIO("\n".join(raw_data[header_index:])), sep=None, engine='python', on_bad_lines='skip')
        df.columns = [c.strip().replace('"', '') for c in df.columns]

        # 3. Mappeur de colonnes (pour éviter les KeyError)
        mapping = {
            'Vitesse': ['GPS_Speed', 'Speed', 'GPS Speed', 'VehicleSpeed', 'Vitesse'],
            'RPM': ['RPM', 'EngineSpeed', 'Eng_RPM', 'Moteur_RPM', 'RPM_Moteur'],
            'Eau': ['Water_Temp', 'WaterTemp', 'ECT', 'Temp_Eau', 'Temp_H2O', 'Water'],
            'EGT': ['EGT', 'Exhaust_Temp', 'Temp_Echap', 'EGT_1'],
            'LatG': ['GPS_LatAcc', 'LatAcc', 'G_Lat', 'Acc_Lat'],
            'LonG': ['GPS_LonAcc', 'LonAcc', 'G_Lon', 'Acc_Lon'],
            'Distance': ['Distance', 'Dist', 'GPS_Distance'],
            'Lap': ['Lap', 'LapNumber', 'Tour', 'Lap_Number']
        }

        found_cols = {}
        for target, aliases in mapping.items():
            for alias in aliases:
                if alias in df.columns:
                    df = df.rename(columns={alias: target})
                    found_cols[target] = True
                    break

        # Vérification des colonnes vitales
        if 'Vitesse' not in df.columns or 'RPM' not in df.columns:
            st.error(f"❌ Colonnes critiques introuvables. Trouvées : {list(df.columns)}")
            st.stop()

        # Nettoyage numérique
        for col in df.columns:
            if col in mapping.keys():
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['Vitesse', 'RPM'])

        # --- ANALYSE PAR TOUR ---
        st.header("📊 Analyse de la Session")
        
        if 'Lap' in df.columns:
            laps = sorted(df['Lap'].dropna().unique().astype(int))
            # Tableau récapitulatif
            summary = []
            for l in laps:
                lap_df = df[df['Lap'] == l]
                summary.append({
                    "Tour": l,
                    "Vmax": lap_df['Vitesse'].max(),
                    "RPM Max": lap_df['RPM'].max(),
                    "Temp Eau Max": lap_df['Eau'].max() if 'Eau' in df.columns else 0
                })
            st.table(pd.DataFrame(summary))
            
            sel_lap = st.select_slider("Zoomer sur un tour", options=laps)
            df_view = df[df['Lap'] == sel_lap]
        else:
            df_view = df
            st.info("Note: Aucune colonne 'Lap' détectée, affichage du roulage continu.")

        # --- METRICS & GRAPHS ---
        m1, m2, m3 = st.columns(3)
        m1.metric("Vmax (Session)", f"{df['Vitesse'].max():.1f} km/h")
        m2.metric("RPM Max (Session)", f"{df['RPM'].max():.0f}")
        if 'Eau' in df.columns: m3.metric("Temp Eau Max", f"{df['Eau'].max():.1f} °C")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_view['Distance'] if 'Distance' in df_view.columns else df_view.index, 
                                 y=df_view['Vitesse'], name="Vitesse", line=dict(color='cyan')))
        fig.add_trace(go.Scatter(x=df_view['Distance'] if 'Distance' in df_view.columns else df_view.index, 
                                 y=df_view['RPM'], name="RPM", yaxis="y2", line=dict(color='orange', dash='dot')))
        fig.update_layout(yaxis2=dict(overlaying='y', side='right'), hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        # --- VERDICT IA ---
        st.subheader("🤖 Verdict de l'Ingénieur")
        conseils = []
        max_rpm_session = df['RPM'].max()
        
        if category == "Rotax 125 Junior (J125)":
            if max_rpm_session > 13800: conseils.append("⚠️ Rapport trop COURT : tu satures trop tôt.")
            elif max_rpm_session < 13200: conseils.append("⚠️ Rapport trop LONG : tu n'atteins pas la puissance max.")
        
        if 'Eau' in df.columns and df['Eau'].max() > 60:
            conseils.append("🔥 Moteur trop chaud : Vérifie le radiateur.")

        for c in conseils:
            st.warning(c)

    except Exception as e:
        st.error(f"❌ Erreur critique : {e}")

else:
    st.info("En attente d'un fichier CSV...")
    
    # Calcul des métriques
    max_speed = df['GPS_Speed'].max()
    max_rpm = df['RPM'].max()
    temp_eau = df['Water_Temp'].max() if 'Water_Temp' in df.columns else 0
    temp_egt = df['EGT'].max() if 'EGT' in df.columns else 0
    max_lat_g = df['GPS_LatAcc'].abs().max()

    # Affichage Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Vmax", f"{max_speed:.1f} km/h")
    m2.metric("RPM Max", f"{max_rpm:.0f}")
    m3.metric("Temp Eau", f"{temp_eau:.1f} °C")
    m4.metric("EGT Max", f"{temp_egt:.0f} °C")

    # Graphiques
    st.divider()
    t1, t2 = st.tabs(["📈 Télémétrie", "🎯 Grip (G-G)"])
    with t1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['Distance'], y=df['GPS_Speed'], name="Vitesse", line=dict(color='cyan')))
        fig.add_trace(go.Scatter(x=df['Distance'], y=df['RPM']/100, name="RPM/100", line=dict(color='orange')))
        st.plotly_chart(fig, use_container_width=True)
        
    with t2:
        fig_gg = px.scatter(df, x='GPS_LatAcc', y='GPS_LonAcc', color='GPS_Speed', range_x=[-3,3], range_y=[-3,3])
        st.plotly_chart(fig_gg)
        

    # Verdict IA
    st.header("🤖 Verdict de l'Ingénieur")
    conseils = []
    
    if category == "Rotax 125 Junior (J125)":
        if max_rpm > 13800: conseils.append("Rapport trop court : Le J125 sature. Enlève 1-2 dents.")
        elif max_rpm < 13200: conseils.append("Rapport trop long : Ajoute des dents.")
        if temp_eau < 48: conseils.append("Moteur trop froid (Cible: 50°C). Masque le radiateur.")
    elif category == "Mini 60":
        if max_rpm > 14600: conseils.append("RPM trop haut : Rallonge la transmission.")
        
    if temp_egt > 670: conseils.append("🔥 CARBURATION TROP PAUVRE : Augmente le gicleur !")
    elif temp_egt < 570 and temp_egt > 0: conseils.append("💧 Trop riche : Réduis le gicleur.")

    if not conseils: st.success("✅ Setup et pilotage optimaux !")
    else:
        for c in conseils: st.write(f"- {c}")

    # Sauvegarde Session
    st.divider()
    with st.expander("💾 Enregistrer dans l'historique"):
        c_name = st.text_input("Circuit")
        c_time = st.text_input("Temps au tour")
        c_dent = st.number_input("Couronne", value=80)
        if st.button("Sauvegarder la session"):
            conn = sqlite3.connect('karting_history.db')
            c = conn.cursor()
            c.execute("INSERT INTO sessions (date, circuit, categorie, chrono, gicleur, couronne, vmax, rpm_max, verdict) VALUES (?,?,?,?,?,?,?,?,?)",
                      (datetime.now().strftime("%d/%m/%Y"), c_name, category, c_time, g_actuel, c_dent, max_speed, max_rpm, str(conseils)))
            conn.commit()
            st.success("Enregistré !")

# Affichage Historique
st.divider()
st.header("📚 Historique des réglages")
conn = sqlite3.connect('karting_history.db')
df_hist = pd.read_sql("SELECT * FROM sessions ORDER BY id DESC", conn)
st.dataframe(df_hist)
