import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from io import StringIO

# --- CONFIGURATION ---
st.set_page_config(page_title="Karting AI Pro - Expert Data", layout="wide", page_icon="🏁")

# --- BARRE LATÉRALE ---
with st.sidebar:
    st.title("🏁 Setup & Météo")
    category = st.selectbox("Moteur", ["Mini 60", "Rotax J125", "Rotax Senior"])
    st.divider()
    t_air = st.slider("Température Air (°C)", -5, 45, 20)
    pignon = st.number_input("Pignon", value=12)
    couronne = st.number_input("Couronne actuelle", value=80)
    
    st.divider()
    st.subheader("🛠️ Réglages Châssis")
    largeur_ar = st.slider("Largeur Arrière (cm)", 130, 140, 139)
    durete_arbre = st.selectbox("Arbre", ["Souple", "Médium", "Dur"])

# --- FONCTIONS DE CALCUL ---
def analyze_braking(df):
    # On détecte le freinage par la décélération longitudinale (GPS_LonAcc < -0.5G)
    if 'LonG' in df.columns:
        return df[df['LonG'] < -0.5]
    return pd.DataFrame()

# --- INTERFACE PRINCIPALE ---
st.title("🏎️ Karting AI Telemetry Analyzer")

file_user = st.file_uploader("📂 Téléverser le fichier CSV AiM", type=["csv"])

if file_user:
    try:
        raw_bytes = file_user.read()
        content = raw_bytes.decode('utf-8', errors='ignore').splitlines()
        
        # Détection Header et Séparateur
        header_index, separator = 0, ","
        for i, line in enumerate(content):
            if any(k in line for k in ["Distance", "Speed", "RPM", "GPS", "Vitesse"]):
                header_index = i
                if line.count(';') > line.count(','): separator = ";"
                break
        
        df = pd.read_csv(StringIO("\n".join(content[header_index:])), sep=separator, engine='python', on_bad_lines='skip')
        df.columns = [c.strip().replace('"', '') for c in df.columns]

        # Mappeur Étendu
        mapping = {
            'Vitesse': ['GPS_Speed', 'Speed', 'GPS Speed', 'Vitesse', 'V_GPS'],
            'RPM': ['RPM', 'EngineSpeed', 'Eng_RPM', 'Moteur_RPM'],
            'Eau': ['Water_Temp', 'WaterTemp', 'Temp_Eau', 'Water'],
            'Distance': ['Distance', 'Dist', 'GPS_Distance'],
            'Lap': ['Lap', 'LapNumber', 'Tour', 'Lap_No'],
            'LonG': ['GPS_LonAcc', 'LonAcc', 'G_Lon', 'Acc_Lon'],
            'LatG': ['GPS_LatAcc', 'LatAcc', 'G_Lat', 'Acc_Lat'],
            'Volant': ['Steer', 'SteerAngle', 'Angle_Volant', 'Steer_Pos']
        }

        for target, aliases in mapping.items():
            for alias in aliases:
                if alias in df.columns:
                    df = df.rename(columns={alias: target})
                    break

        # Nettoyage
        for col in ['Vitesse', 'RPM', 'Distance', 'Lap', 'LonG', 'LatG', 'Volant']:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['Vitesse', 'RPM'])
        if 'Lap' not in df.columns or df['Lap'].nunique() <= 1:
            df['Lap'] = (df['Distance'].diff() < 0).cumsum() + 1

        # --- SECTION ANALYSE PERFORMANCE ---
        laps = sorted(df['Lap'].dropna().unique().astype(int))
        if len(laps) > 1:
            st.header("⚔️ Comparaison de Tours & Analyse Virages")
            c1, c2 = st.columns(2)
            tour_a = c1.selectbox("Tour de Référence (A)", laps, index=0)
            tour_b = c2.selectbox("Tour à Comparer (B)", laps, index=len(laps)-1)

            df_a = df[df['Lap'] == tour_a].copy()
            df_b = df[df['Lap'] == tour_b].copy()
            
            # Normalisation Distance
            df_a['D_Norm'] = df_a['Distance'] - df_a['Distance'].min()
            df_b['D_Norm'] = df_b['Distance'] - df_b['Distance'].min()

            # --- CALCUL DU TIME DELTA (Temps gagné/perdu) ---
            # Interpolation pour comparer les vitesses sur la même base de distance
            common_dist = np.linspace(0, min(df_a['D_Norm'].max(), df_b['D_Norm'].max()), 500)
            v_a = np.interp(common_dist, df_a['D_Norm'], df_a['Vitesse']) / 3.6
            v_b = np.interp(common_dist, df_b['D_Norm'], df_b['Vitesse']) / 3.6
            
            # Temps = Distance / Vitesse -> Somme cumulative de la différence
            dt_a = np.diff(common_dist, prepend=0) / v_a
            dt_b = np.diff(common_dist, prepend=0) / v_b
            time_delta = np.cumsum(dt_b - dt_a)

            # --- GRAPHIQUES ---
            fig = go.Figure()
            # Vitesse
            fig.add_trace(go.Scatter(x=df_a['D_Norm'], y=df_a['Vitesse'], name=f"Vitesse T{tour_a}", line=dict(color='#00CCFF')))
            fig.add_trace(go.Scatter(x=df_b['D_Norm'], y=df_b['Vitesse'], name=f"Vitesse T{tour_b}", line=dict(color='#FF3300', dash='dash')))
            # Time Delta (Axe secondaire)
            fig.add_trace(go.Scatter(x=common_dist, y=time_delta, name="Ecart de Temps (sec)", yaxis="y2", fill='tozeroy', line=dict(color='rgba(255,255,255,0.3)')))
            
            fig.update_layout(
                yaxis2=dict(title="Delta (sec)", overlaying='y', side='right', zeroline=True, zerolinecolor='white'),
                hovermode="x unified", template="plotly_dark", title="Analyse comparative : Vitesse vs Delta"
            )
            st.plotly_chart(fig, use_container_width=True)
            

            # --- ANALYSE PILOTAGE ---
            st.subheader("🧠 Analyse du Pilotage")
            col_p1, col_p2 = st.columns(2)
            
            with col_p1:
                st.write("**Freinage & Grip :**")
                if 'LonG' in df_b.columns:
                    st.write(f"- Décélération Max : {df_b['LonG'].min():.2f} G")
                    if df_b['LonG'].min() > -1.0: st.info("💡 Tu peux freiner plus fort ! Cible -1.2G.")
                if 'LatG' in df_b.columns:
                    st.write(f"- Grip Latéral Max : {df_b['LatG'].abs().max():.2f} G")

            with col_p2:
                st.write("**Travail du Volant :**")
                if 'Volant' in df_b.columns:
                    fig_volant = px.line(df_b, x='Distance', y='Volant', title="Angle de Volant")
                    st.plotly_chart(fig_volant, use_container_width=True)
                else:
                    st.info("Angle de volant non détecté (Capteur requis).")

            # --- CONSEILS RÉGLAGES ---
            st.divider()
            st.header("🛠️ Préconisations de l'Ingénieur")
            
            # Analyse Gearing (Rapport)
            rpm_max = df_b['RPM'].max()
            vmax = df_b['Vitesse'].max()
            
            c_r1, c_r2 = st.columns(2)
            with c_r1:
                st.subheader("Moteur & Rapport")
                if category == "Rotax J125":
                    if rpm_max > 13900: st.error(f"Saturation ({int(rpm_max)} RPM). Enlève 1 dent.")
                    elif rpm_max < 13400: st.warning(f"Sous-régime ({int(rpm_max)} RPM). Ajoute 1-2 dents.")
                    else: st.success("Rapport de boîte parfait !")
            
            with c_r2:
                st.subheader("Châssis")
                if 'LatG' in df_b.columns and df_b['LatG'].abs().max() < 1.8:
                    st.write("- **Manque de grip latéral :**")
                    st.write("  - Resserre l'avant (plus de directivité)")
                    st.write("  - Élargis l'arrière (stabilité)")
                else:
                    st.write("- **Équilibre général :**")
                    st.write("  - Si le kart sautille : Arbre plus souple.")
                    st.write("  - Si le kart glisse : Resserre l'arrière.")

    except Exception as e:
        st.error(f"❌ Erreur lors de l'analyse : {e}")
