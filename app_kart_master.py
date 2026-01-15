import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from io import StringIO
import sqlite3

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
    st.subheader("🌤️ Conditions & Setup")
    t_air = st.slider("Température Air (°C)", -5, 45, 20)
    pression_pneus = st.number_input("Pression à froid (Bar)", value=0.50, step=0.01)
    g_actuel = st.number_input("Gicleur actuel", value=122)
    
    if "Rotax" in category:
        g_suggere = int(g_actuel + (20 - t_air) / 5)
        st.warning(f"🔧 Gicleur suggéré : **{g_suggere}**")
    
    st.divider()
    st.info("💡 **Export AiM :** Utilisez le format CSV. Assurez-vous d'inclure 'GPS Speed', 'RPM', 'Temp' et 'GPS Accel'.")

# --- INTERFACE PRINCIPALE ---
st.title("🏎️ Karting AI Telemetry Analyzer")

file_user = st.file_uploader("📂 Téléverser le fichier CSV de la Session", type=["csv"])

if file_user:
    try:
        # 1. Lecture brute et détection intelligente du header
        content = file_user.read().decode('utf-8', errors='ignore').splitlines()
        header_index = 0
        sep = ","
        for i, line in enumerate(content):
            if any(k in line for k in ["Distance", "Speed", "RPM", "GPS", "Vitesse"]):
                header_index = i
                if line.count(';') > line.count(','): sep = ";"
                break
        
        # 2. Chargement avec Pandas
        data_str = "\n".join(content[header_index:])
        df = pd.read_csv(StringIO(data_str), sep=sep, engine='python', on_bad_lines='skip')
        df.columns = [c.strip().replace('"', '') for c in df.columns]

        # 3. Mappeur de colonnes (Standardisation)
        mapping = {
            'Vitesse': ['GPS_Speed', 'Speed', 'GPS Speed', 'Vitesse'],
            'RPM': ['RPM', 'EngineSpeed', 'Eng_RPM', 'Moteur_RPM'],
            'Eau': ['Water_Temp', 'WaterTemp', 'Temp_Eau', 'Eau'],
            'LatG': ['GPS_LatAcc', 'LatAcc', 'G_Lat', 'Acc_Lat'],
            'LonG': ['GPS_LonAcc', 'LonAcc', 'G_Lon', 'Acc_Lon'],
            'Distance': ['Distance', 'Dist', 'GPS_Distance'],
            'Lap': ['Lap', 'LapNumber', 'Tour', 'Lap_No'],
            'Time': ['Time', 'Time_sec', 'Temps']
        }

        for target, aliases in mapping.items():
            for alias in aliases:
                if alias in df.columns:
                    df = df.rename(columns={alias: target})
                    break

        # Nettoyage numérique
        cols_to_convert = ['Vitesse', 'RPM', 'Eau', 'Distance', 'Lap', 'LatG', 'LonG', 'Time']
        for col in cols_to_convert:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['Vitesse', 'RPM'])

        # Détection auto des tours si manquants
        if 'Lap' not in df.columns or df['Lap'].nunique() <= 1:
            if 'Distance' in df.columns:
                df['Lap'] = (df['Distance'].diff() < -100).cumsum() + 1
            else:
                df['Lap'] = 1

        # --- ANALYSE DES TOURS ---
        laps = sorted(df['Lap'].dropna().unique().astype(int))
        summary_data = []
        for l in laps:
            lap_df = df[df['Lap'] == l]
            if len(lap_df) > 10:
                # Calcul du temps au tour (si colonne Time présente)
                lap_time = "N/A"
                if 'Time' in lap_df.columns:
                    lap_time_val = lap_df['Time'].max() - lap_df['Time'].min()
                    lap_time = f"{int(lap_time_val//60)}:{lap_time_val%60:06.3f}"
                
                summary_data.append({
                    "Tour": l,
                    "Temps": lap_time,
                    "Vmax": lap_df['Vitesse'].max(),
                    "RPM Max": lap_df['RPM'].max(),
                    "RPM Min": lap_df['RPM'].min(),
                    "Eau Max": lap_df['Eau'].max() if 'Eau' in df.columns else 0,
                    "G-Lat Max": lap_df['LatG'].abs().max() if 'LatG' in df.columns else 0
                })

        summary_df = pd.DataFrame(summary_data)
        
        # Identification du meilleur tour
        best_lap_idx = summary_df['Vmax'].idxmax() # Par défaut sur Vmax si Time absent
        best_lap_num = summary_df.loc[best_lap_idx, 'Tour']

        st.header(f"📊 Analyse de Session : {category}")
        st.subheader(f"🏆 Meilleur Tour Détecté : Tour {best_lap_num}")
        
        with st.expander("📝 Détails de tous les tours", expanded=False):
            st.table(summary_df)

        # --- FOCUS SUR LE TOUR SÉLECTIONNÉ ---
        sel_lap = st.select_slider("Sélectionner un tour pour l'analyse d'expert", options=laps, value=int(best_lap_num))
        df_view = df[df['Lap'] == sel_lap]
        
        # Statistiques spécifiques du tour
        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("Vmax", f"{df_view['Vitesse'].max():.1f} km/h")
        s2.metric("RPM Max", f"{int(df_view['RPM'].max())}")
        s3.metric("RPM Min", f"{int(df_view['RPM'].min())}")
        s4.metric("Eau Max", f"{df_view['Eau'].max():.1f} °C" if 'Eau' in df.columns else "N/A")
        s5.metric("G-Lat Max", f"{df_view['LatG'].abs().max():.2f} G" if 'LatG' in df.columns else "N/A")

        # Graphique
        fig = go.Figure()
        x_ax = df_view['Distance'] if 'Distance' in df_view.columns else df_view.index
        fig.add_trace(go.Scatter(x=x_ax, y=df_view['Vitesse'], name="Vitesse", line=dict(color='cyan')))
        fig.add_trace(go.Scatter(x=x_ax, y=df_view['RPM'], name="RPM", yaxis="y2", line=dict(color='orange', dash='dot')))
        fig.update_layout(template="plotly_dark", yaxis2=dict(overlaying='y', side='right'), hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        # --- SECTION RÉGLAGES EXPERTS ---
        st.divider()
        col_moteur, col_chassis = st.columns(2)

        with col_moteur:
            st.subheader("⚙️ Optimisation Moteur")
            if category == "Rotax 125 Junior (J125)":
                if df_view['RPM'].max() > 13900: st.error("Rapport trop court : Enlevez 1 dent.")
                elif df_view['RPM'].max() < 13400: st.warning("Rapport trop long : Ajoutez 1-2 dents.")
            
            if 'Eau' in df_view.columns:
                if df_view['Eau'].max() > 55: st.error("Chauffe excessive : Ouvrez le rideau de radiateur.")
                elif df_view['Eau'].max() < 45: st.info("Moteur trop froid : Cachez le radiateur (Cible 50°C).")

        with col_chassis:
            st.subheader("🛠️ Guide de Réglages Châssis")
            lat_g = df_view['LatG'].abs().max() if 'LatG' in df_view.columns else 1.5
            
            # Système expert de conseils
            if lat_g < 1.8:
                st.write("**Problème détecté : Manque de Grip Latéral**")
                tabs = st.tabs(["Train Avant", "Train Arrière", "Hauteur/Barre"])
                
                with tabs[0]:
                    st.write("- **Chasse :** Augmenter (plus de grip en entrée).")
                    st.write("- **Carrossage (Camber) :** Mettre plus de négatif.")
                    st.write("- **Largeur :** Élargir le train avant (+1 bague de chaque côté).")
                    st.write("- **Bagues :** Enlever des bagues pour assouplir la fusée.")
                
                with tabs[1]:
                    st.write("- **Axe Arrière :** Passer sur un axe plus souple (type S ou MS).")
                    st.write("- **Largeur :** Rétrécir le train arrière (Cible 139cm max).")
                    st.write("- **Pression :** Augmenter de +50g si les pneus ne montent pas en température.")
                
                with tabs[2]:
                    st.write("- **Hauteur :** Baisser l'arrière et monter l'avant.")
                    st.write("- **Barre Avant :** Mettre la barre **Ronde** ou la barre **Plate en position verticale** pour plus de rigidité.")

            else:
                st.write("**Problème détecté : Trop de Grip / Kart qui saute**")
                st.write("- **Axe :** Passer sur un axe plus dur (type H ou HH).")
                st.write("- **Train Arrière :** Élargir au maximum (140cm).")
                st.write("- **Barre Avant :** Enlever la barre ou mettre la barre plate à l'horizontale.")
                st.write("- **Pression :** Baisser la pression de 0.05 bar.")

    except Exception as e:
        st.error(f"❌ Erreur : {e}")
else:
    st.info("👋 Chargez un fichier CSV pour obtenir l'analyse d'expert.")
