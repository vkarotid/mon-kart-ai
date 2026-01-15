import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from fpdf import FPDF
import sqlite3
from datetime import datetime
from io import StringIO

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Karting AI Pro", layout="wide", page_icon="🏁")

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

# --- BARRE LATÉRALE (SIDEBAR) ---
with st.sidebar:
    st.title("🏁 Configuration")
    category = st.selectbox("Type de Moteur", ["Mini 60", "Rotax 125 Junior (J125)", "Rotax Max (Senior)"], key="motor_select")
    
    st.divider()
    st.subheader("🌤️ Conditions Météo")
    t_air = st.slider("Température Air (°C)", -5, 45, 20)
    g_actuel = st.number_input("Gicleur actuel", value=122)
    
    if "Rotax" in category:
        g_suggere = int(g_actuel + (20 - t_air) / 5)
        st.warning(f"🔧 Gicleur suggéré : **{g_suggere}**")
    
    st.divider()
    st.info("💡 **Export AiM :** Utilisez le format CSV avec 'Comma' comme séparateur.")

# --- INTERFACE PRINCIPALE ---
st.title("🏎️ Karting AI Telemetry Analyzer")

file_user = st.file_uploader("📂 Téléverser le fichier CSV de la Session", type=["csv"])

if file_user:
    try:
        # 1. Lecture brute et détection intelligente du header
        raw_content = file_user.read().decode('utf-8').splitlines()
        header_index = 0
        for i, line in enumerate(raw_content):
            if any(k in line for k in ["Distance", "Speed", "RPM", "GPS", "Lap"]):
                header_index = i
                break
        
        # 2. Chargement avec Pandas (Gestion des lignes malformées)
        data_str = "\n".join(raw_content[header_index:])
        df = pd.read_csv(StringIO(data_str), sep=None, engine='python', on_bad_lines='skip')
        
        # Nettoyage des noms de colonnes (espaces et guillemets)
        df.columns = [c.strip().replace('"', '') for c in df.columns]

        # 3. Mappeur de colonnes (Standardisation)
        mapping = {
            'Vitesse': ['GPS_Speed', 'Speed', 'GPS Speed', 'VehicleSpeed', 'Vitesse'],
            'RPM': ['RPM', 'EngineSpeed', 'Eng_RPM', 'Moteur_RPM', 'RPM_Moteur'],
            'Eau': ['Water_Temp', 'WaterTemp', 'ECT', 'Temp_Eau', 'Temp_H2O', 'Water'],
            'EGT': ['EGT', 'Exhaust_Temp', 'Temp_Echap', 'EGT_1'],
            'LatG': ['GPS_LatAcc', 'LatAcc', 'G_Lat', 'Acc_Lat'],
            'LonG': ['GPS_LonAcc', 'LonAcc', 'G_Lon', 'Acc_Lon'],
            'Distance': ['Distance', 'Dist', 'GPS_Distance'],
            'Lap': ['Lap', 'LapNumber', 'Tour', 'Lap_Number', 'Lap_No']
        }

        found_map = {}
        for target, aliases in mapping.items():
            for alias in aliases:
                if alias in df.columns:
                    df = df.rename(columns={alias: target})
                    found_map[target] = True
                    break

        # Vérification des données minimales
        if 'Vitesse' not in df.columns or 'RPM' not in df.columns:
            st.error(f"❌ Colonnes critiques manquantes. Trouvées : {list(df.columns)}")
            st.stop()

        # 4. Nettoyage numérique
        cols_to_convert = ['Vitesse', 'RPM', 'Eau', 'EGT', 'Distance', 'Lap', 'LatG', 'LonG']
        for col in cols_to_convert:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df.dropna(subset=['Vitesse', 'RPM'])

        # --- ANALYSE GLOBALE ET PAR TOUR ---
        st.header(f"📊 Analyse de Session : {category}")
        
        # Section récapitulative tour par tour
        if 'Lap' in df.columns and df['Lap'].nunique() > 1:
            laps = sorted(df['Lap'].dropna().unique().astype(int))
            
            with st.expander("📝 Tableau Récapitulatif de la Session", expanded=True):
                summary_data = []
                for l in laps:
                    lap_df = df[df['Lap'] == l]
                    if not lap_df.empty:
                        summary_data.append({
                            "Tour": l,
                            "Vmax (km/h)": round(lap_df['Vitesse'].max(), 1),
                            "RPM Max": int(lap_df['RPM'].max()),
                            "Eau Max": round(lap_df['Eau'].max(), 1) if 'Eau' in df.columns else "N/A"
                        })
                st.table(pd.DataFrame(summary_data))
            
            sel_lap = st.select_slider("Choisir un tour pour l'analyse détaillée", options=laps, key="main_lap_slider")
            df_view = df[df['Lap'] == sel_lap]
        else:
            df_view = df
            st.info("💡 Note : Données continues. Pour une analyse tour par tour, exportez la colonne 'Lap' depuis RaceStudio.")

        # --- AFFICHAGE DES GRAPHIQUES ---
        st.divider()
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Vmax (Session)", f"{df['Vitesse'].max():.1f} km/h")
        col_m2.metric("RPM Max (Session)", f"{df['RPM'].max():.0f}")
        if 'Eau' in df.columns:
            col_m3.metric("Temp. Eau Max", f"{df['Eau'].max():.1f} °C")

        # Graphique principal
        fig = go.Figure()
        x_axis = df_view['Distance'] if 'Distance' in df_view.columns else df_view.index
        
        fig.add_trace(go.Scatter(x=x_axis, y=df_view['Vitesse'], name="Vitesse (km/h)", line=dict(color='cyan', width=2)))
        fig.add_trace(go.Scatter(x=x_axis, y=df_view['RPM'], name="RPM", yaxis="y2", line=dict(color='orange', dash='dot')))
        
        fig.update_layout(
            title=f"Télémétrie Détail",
            xaxis=dict(title="Distance (m)"),
            yaxis=dict(title="Vitesse (km/h)", gridcolor='gray'),
            yaxis2=dict(title="RPM", overlaying='y', side='right'),
            hovermode="x unified",
            template="plotly_dark"
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- VERDICT IA ---
        st.subheader("🤖 Verdict de l'Ingénieur")
        conseils = []
        
        # Logique spécifique Rotax J125
        if category == "Rotax 125 Junior (J125)":
            max_rpm_val = df_view['RPM'].max()
            if max_rpm_val > 13800:
                conseils.append("❌ **Rapport trop COURT :** Le moteur sature trop tôt en ligne droite. Enlève 1 ou 2 dents à la couronne.")
            elif max_rpm_val < 13200:
                conseils.append("⚠️ **Rapport trop LONG :** Tu n'atteins pas le régime de puissance max. Ajoute des dents.")
        
        # Logique Température
        if 'Eau' in df.columns:
            temp_max = df['Eau'].max()
            if temp_max > 60:
                conseils.append("🔥 **ALERTE CHAUFFE :** Ton moteur a dépassé 60°C. Vérifie le radiateur ou le débit d'eau.")
            elif temp_max < 45:
                conseils.append("🔵 **MOTEUR FROID :** Température sous 45°C. Masque ton radiateur pour gagner en performance.")

        if not conseils:
            st.success("✅ Les paramètres moteur semblent optimaux sur ce roulage.")
        else:
            for c in conseils:
                st.write(c)

    except Exception as e:
        st.error(f"❌ Erreur lors de l'analyse : {e}")
        st.info("Vérifiez le format de votre fichier CSV exporté.")

else:
    st.info("👋 En attente d'un fichier CSV... Exportez vos données depuis AiM RaceStudio pour commencer.")
