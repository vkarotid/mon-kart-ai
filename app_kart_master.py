# 4. Nettoyage et sécurisation des colonnes vitales
        for col in ['Vitesse', 'RPM', 'Eau', 'Distance', 'Lap', 'LonG', 'LatG', 'Volant', 'Time']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df.dropna(subset=['Vitesse', 'RPM'])

        # --- SÉCURITÉ : CRÉATION DE LA DISTANCE SI MANQUANTE ---
        if 'Distance' not in df.columns:
            st.warning("⚠️ Colonne 'Distance' manquante. Calcul automatique via la vitesse...")
            # Si on a le temps, on calcule : Distance = Vitesse * Temps
            if 'Time' in df.columns:
                df['Distance'] = (df['Vitesse'] / 3.6) * df['Time'].diff().fillna(0).cumsum()
            else:
                # Sinon on simule une distance basée sur l'échantillonnage (fréquence 10Hz par défaut)
                df['Distance'] = (df['Vitesse'] / 3.6 * 0.1).cumsum()

        # --- SÉCURITÉ : CRÉATION DES TOURS ---
        if 'Lap' not in df.columns or df['Lap'].nunique() <= 1:
            # On détecte le passage de ligne quand la distance revient à zéro ou fait un saut
            df['Lap'] = (df['Distance'].diff() < -100).cumsum() + 1
