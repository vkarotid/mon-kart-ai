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

if file_user:
    # --- NETTOYAGE DU FICHIER AIM ---
    # On lit le fichier ligne par ligne pour trouver l'en-tête réel
    lines = file_user.readlines()
    header_row = 0
    for i, line in enumerate(lines):
        decoded_line = line.decode('utf-8')
        # On cherche la ligne qui contient les mots clés de télémétrie
        if "Distance" in decoded_line or "GPS_Speed" in decoded_line:
            header_row = i
            break
    
    # On remet le pointeur au début du fichier pour pandas
    file_user.seek(0)
    
    # On lit le CSV en sautant les lignes inutiles trouvées
    try:
        df = pd.read_csv(file_user, sep=None, engine='python', skiprows=header_row)
        
        # Nettoyage des noms de colonnes (parfois AiM ajoute des espaces)
        df.columns = [c.strip() for c in df.columns]
        
        st.success(f"Fichier chargé ! {len(df)} points de données détectés.")
    except Exception as e:
        st.error(f"Erreur lors de la lecture du CSV : {e}")
        st.stop()
    
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
