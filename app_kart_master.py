import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from io import StringIO

st.set_page_config(page_title="Karting AI Pro", layout="wide")

# --- FONCTION DE NETTOYAGE AGRESSIF ---
def clean_aim_csv(uploaded_file):
    # Lire tout le contenu
    raw_bytes = uploaded_file.read()
    content = raw_bytes.decode('utf-8', errors='ignore').splitlines()
    
    # 1. Trouver la ligne des titres (Header)
    # On cherche la ligne qui contient le plus de mots-clés de télémétrie
    header_idx = -1
    sep = ","
    for i, line in enumerate(content):
        if "Speed" in line or "Vitesse" in line or "RPM" in line:
            header_idx = i
            # Détecter le séparateur sur cette ligne précise
            sep = ";" if line.count(";") > line.count(",") else ","
            break
            
    if header_idx == -1:
        return None, "Impossible de trouver l'en-tête des données."

    # 2. Filtrer pour ne garder que les lignes de données
    # Les données commencent après le header et ne contiennent que des chiffres/points/virgules
    data_lines = [content[header_idx]] # On garde le titre
    for line in content[header_idx + 1:]:
        # On vérifie si la ligne commence par un chiffre ou un signe (ex: distance ou temps)
        # Cela permet d'ignorer les lignes de texte de RaceStudio en fin de fichier
        clean_line = line.strip()
        if clean_line and (clean_line[0].isdigit() or clean_line[0] in ['-', '.']):
            data_lines.append(line)
            
    return pd.read_csv(StringIO("\n".join(data_lines)), sep=sep, engine='python', on_bad_lines='skip'), None

# --- INTERFACE ---
st.title("🏁 Analyseur Karting Expert")
st.info("Exportez votre CSV depuis RaceStudio 3 sans vous soucier des réglages, l'IA s'occupe du nettoyage.")

file = st.file_uploader("Fichier CSV AiM", type=["csv"])

if file:
    df, error = clean_aim_csv(file)
    
    if error:
        st.error(error)
    else:
        # Nettoyage des colonnes (suppression des espaces et guillemets)
        df.columns = [c.strip().replace('"', '') for c in df.columns]
        
        # Mappeur Flexible
        mapping = {
            'V': ['GPS_Speed', 'Speed', 'Vitesse', 'V_GPS'],
            'R': ['RPM', 'EngineSpeed', 'Eng_RPM', 'Moteur_RPM'],
            'D': ['Distance', 'Dist', 'GPS_Distance'],
            'L': ['Lap', 'LapNumber', 'Tour', 'Lap_No']
        }
        
        for target, aliases in mapping.items():
            for alias in aliases:
                if alias in df.columns:
                    df = df.rename(columns={alias: target})
                    break
        
        # Conversion forcée en numérique
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['V', 'R'])

        # Auto-calcul des tours si manquants
        if 'L' not in df.columns or df['L'].nunique() <= 1:
             if 'D' in df.columns:
                 df['L'] = (df['D'].diff() < -50).cumsum() + 1
             else:
                 df['L'] = 1

        # --- AFFICHAGE ---
        laps = sorted(df['L'].unique().astype(int))
        st.success(f"Fichier chargé : {len(laps)} tours détectés.")
        
        col1, col2 = st.columns(2)
        t1 = col1.selectbox("Tour Référence", laps, index=0)
        t2 = col2.selectbox("Tour à comparer", laps, index=len(laps)-1)

        # Graphique Simple de Superposition
        d1 = df[df['L'] == t1].copy()
        d2 = df[df['L'] == t2].copy()
        
        # Normalisation distance
        d1['Dist_N'] = d1['D'] - d1['D'].min() if 'D' in d1.columns else d1.index
        d2['Dist_N'] = d2['D'] - d2['D'].min() if 'D' in d2.columns else d2.index

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=d1['Dist_N'], y=d1['V'], name=f"Tour {t1}", line=dict(color='cyan')))
        fig.add_trace(go.Scatter(x=d2['Dist_N'], y=d2['V'], name=f"Tour {t2}", line=dict(color='orange')))
        fig.update_layout(template="plotly_dark", xaxis_title="Distance (m)", yaxis_title="Vitesse (km/h)")
        st.plotly_chart(fig, use_container_width=True)

        # Diagnostic Rapide
        vmax = d2['V'].max()
        st.metric("Vmax du tour sélectionné", f"{vmax:.1f} km/h")
